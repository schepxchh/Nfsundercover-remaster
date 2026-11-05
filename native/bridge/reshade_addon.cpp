// SPDX-License-Identifier: MIT
// Official ReShade SDK event bridge. No proxy exports, hooks or game addresses.
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>
#include <d3d9.h>
#include <reshade.hpp>

#include "nfsuc/core.hpp"
#include "nfsuc/dx9_renderer.hpp"
#include "nfsuc/shader_registry.hpp"

#include <atomic>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

static_assert(sizeof(void *) == 4, "NFS Undercover requires the Win32 .addon32 target");

// NAME/DESCRIPTION are reserved .def directives. Explicit x86 C aliases provide
// the SDK's undecorated data names without ambiguous .def parsing/decoration.
#if defined(_MSC_VER) && defined(_M_IX86)
#pragma comment(linker, "/EXPORT:NAME=_NAME,DATA")
#pragma comment(linker, "/EXPORT:DESCRIPTION=_DESCRIPTION,DATA")
#define NFSUC_METADATA_EXPORT
#else
#define NFSUC_METADATA_EXPORT __declspec(dllexport)
#endif
extern "C" NFSUC_METADATA_EXPORT const char *NAME = "NFSUC Native Visual Foundation";
extern "C" NFSUC_METADATA_EXPORT const char *DESCRIPTION =
    "Experimental native DX9 SDR grade; disabled by default, visual-only.";
#undef NFSUC_METADATA_EXPORT

namespace {
using Runtime = reshade::api::effect_runtime;
using Device = reshade::api::device;

struct RuntimeState {
    Device *device = nullptr; // Borrowed SDK identity; never dereferenced after destroy callback.
    nfsuc::Config config;
    nfsuc::Dx9Renderer renderer;
    std::uint64_t presents = 0;
    bool error_reported = false;
};

// ReShade dispatches reset/present callbacks; this also serializes multiple runtimes.
std::mutex state_mutex;
std::unordered_map<Runtime *, std::unique_ptr<RuntimeState>> runtimes;
std::filesystem::path config_path;
nfsuc::Config addon_config;
std::mutex shader_mutex;
std::unique_ptr<nfsuc::ShaderRegistry> shader_registry;
std::atomic<std::uint64_t> pipelines_destroyed{0};
bool registered = false;

void log_info(const char *text) noexcept {
    reshade::log::message(reshade::log::level::info, text);
}
void log_warning(const char *text) noexcept {
    reshade::log::message(reshade::log::level::warning, text);
}

std::filesystem::path module_path(HMODULE module) {
    std::vector<wchar_t> text(32768);
    const DWORD count = GetModuleFileNameW(module, text.data(), static_cast<DWORD>(text.size()));
    if (count == 0 || count >= text.size()) return {};
    return std::filesystem::path(std::wstring(text.data(), count));
}

bool is_undercover_process() {
    const auto path = module_path(nullptr);
    return !path.empty() && _wcsicmp(path.filename().c_str(), L"nfs.exe") == 0;
}

nfsuc::Config load_config() {
    nfsuc::Config disabled;
    std::error_code ec;
    const auto size = std::filesystem::file_size(config_path, ec);
    if (ec) {
        log_info("NFSUC Native: no readable NFSUCNative.ini; observe-only default.");
        return disabled;
    }
    if (size > 65536) {
        log_warning("NFSUC Native: config exceeds 64 KiB; rendering disabled.");
        return disabled;
    }
    std::ifstream file(config_path, std::ios::binary);
    if (!file) {
        log_warning("NFSUC Native: cannot open config; rendering disabled.");
        return disabled;
    }
    std::string text(static_cast<std::size_t>(size), '\0');
    if (size && !file.read(text.data(), static_cast<std::streamsize>(size))) {
        log_warning("NFSUC Native: incomplete config read; rendering disabled.");
        return disabled;
    }
    auto result = nfsuc::parse_config(text);
    if (!result.ok()) {
        log_warning("NFSUC Native: invalid config; all native changes disabled.");
        for (const auto &error : result.errors)
            reshade::log::message(reshade::log::level::warning, error.c_str());
        return disabled;
    }
    return result.value;
}

void report_runtime(const RuntimeState &state) noexcept {
    const auto stats = state.renderer.stats();
    char text[256];
    std::snprintf(text, sizeof(text),
        "NFSUC Native: runtime released; presents=%llu rendered=%llu skipped=%llu last_hresult=0x%08lX.",
        static_cast<unsigned long long>(state.presents),
        static_cast<unsigned long long>(stats.frames_rendered),
        static_cast<unsigned long long>(stats.frames_skipped),
        static_cast<unsigned long>(stats.last_error));
    log_info(text);
}

void on_init_effect_runtime(Runtime *runtime) noexcept {
    try {
        if (!runtime || runtime->get_device()->get_api() != reshade::api::device_api::d3d9)
            return;
        auto state = std::make_unique<RuntimeState>();
        state->device = runtime->get_device();
        state->config = addon_config;
        log_info(state->config.enabled
            ? "NFSUC Native: DX9 runtime registered; experimental native grade ENABLED. Disable other grades for A/B."
            : "NFSUC Native: DX9 runtime registered in observe-only mode; no GPU rendering.");
        std::lock_guard<std::mutex> lock(state_mutex);
        const auto old = runtimes.find(runtime);
        if (old != runtimes.end()) old->second->renderer.release();
        runtimes[runtime] = std::move(state);
    } catch (...) {
        log_warning("NFSUC Native: runtime initialization failed; no native rendering.");
    }
}

void on_destroy_effect_runtime(Runtime *runtime) noexcept {
    try {
        std::lock_guard<std::mutex> lock(state_mutex);
        const auto it = runtimes.find(runtime);
        if (it == runtimes.end()) return;
        report_runtime(*it->second);
        it->second->renderer.release();
        runtimes.erase(it);
    } catch (...) {
        log_warning("NFSUC Native: exception during runtime cleanup.");
    }
}

void release_device_states(Device *device) noexcept {
    try {
        std::lock_guard<std::mutex> lock(state_mutex);
        for (auto it = runtimes.begin(); it != runtimes.end();) {
            if (it->second->device == device) {
                report_runtime(*it->second);
                it->second->renderer.release();
                it = runtimes.erase(it);
            } else ++it;
        }
    } catch (...) {
        log_warning("NFSUC Native: exception during device cleanup.");
    }
}

void on_destroy_swapchain(reshade::api::swapchain *swapchain, bool /*resize*/) noexcept {
    // SDK guarantees this before DX9 Reset/ResetEx. Remove all states on this
    // device conservatively, avoiding any default-pool references blocking Reset.
    if (swapchain) release_device_states(swapchain->get_device());
}

void on_destroy_device(Device *device) noexcept { release_device_states(device); }

void on_init_pipeline(Device *device, reshade::api::pipeline_layout /*layout*/,
    std::uint32_t subobject_count, const reshade::api::pipeline_subobject *subobjects,
    reshade::api::pipeline /*pipeline*/) noexcept {
    try {
        if (!addon_config.observe_shaders || !device || !subobjects ||
            device->get_api() != reshade::api::device_api::d3d9) return;
        std::lock_guard<std::mutex> lock(shader_mutex);
        if (!shader_registry) return;
        // The SDK owns this bytecode only for the duration of the callback.
        // Registry hashes metadata synchronously; no bytes or pipeline handles survive.
        for (std::uint32_t i = 0; i < subobject_count; ++i) {
            const auto &subobject = subobjects[i];
            if (subobject.count != 1 || !subobject.data) continue;
            nfsuc::ShaderStage stage;
            if (subobject.type == reshade::api::pipeline_subobject_type::pixel_shader)
                stage = nfsuc::ShaderStage::pixel;
            else if (subobject.type == reshade::api::pipeline_subobject_type::vertex_shader)
                stage = nfsuc::ShaderStage::vertex;
            else continue;
            const auto &shader = *static_cast<const reshade::api::shader_desc *>(subobject.data);
            shader_registry->observe(stage, shader.code, shader.code_size);
        }
    } catch (...) {
        log_warning("NFSUC Native: shader metadata observation failed; game shader unchanged.");
    }
}

void on_destroy_pipeline(Device *device, reshade::api::pipeline /*pipeline*/) noexcept {
    if (addon_config.observe_shaders && device &&
        device->get_api() == reshade::api::device_api::d3d9)
        ++pipelines_destroyed; // Metadata only; no resource release or shader replacement.
}

void report_shader_registry() {
    std::lock_guard<std::mutex> lock(shader_mutex);
    if (!shader_registry || !addon_config.observe_shaders) return;
    const auto records = shader_registry->snapshot();
    char text[256];
    std::snprintf(text, sizeof(text),
        "NFSUC Native: passive shader metadata records=%llu destroyed_pipelines=%llu; FNV1a64 grouping only, no semantic identification.",
        static_cast<unsigned long long>(records.size()),
        static_cast<unsigned long long>(pipelines_destroyed.load()));
    log_info(text);
    for (const auto &record : records) {
        std::snprintf(text, sizeof(text),
            "NFSUC Native shader: stage=%s fnv1a64=%016llX bytes=%llu version=0x%08lX observations=%llu.",
            record.stage == nfsuc::ShaderStage::pixel ? "PS" : "VS",
            static_cast<unsigned long long>(record.hash),
            static_cast<unsigned long long>(record.bytecode_size),
            static_cast<unsigned long>(record.version_token),
            static_cast<unsigned long long>(record.observations));
        log_info(text);
    }
}

void on_reshade_present(Runtime *runtime) noexcept {
    try {
        std::lock_guard<std::mutex> lock(state_mutex);
        const auto it = runtimes.find(runtime);
        if (it == runtimes.end()) return;
        RuntimeState &state = *it->second;
        ++state.presents;
        if (!state.config.enabled) return; // Default does not touch the native device.
        if (state.device->get_api() != reshade::api::device_api::d3d9) return;

        auto *device = reinterpret_cast<IDirect3DDevice9 *>(
            static_cast<std::uintptr_t>(state.device->get_native()));
        if (!device) return;
        if (FAILED(device->TestCooperativeLevel())) {
            state.renderer.release();
            return;
        }

        // Pinned ReShade D3D9 swapchain::get_back_buffer returns a native
        // IDirect3DResource9 pointing to its surface. Do not decode resource_view
        // flag bits or assume that arbitrary resource handles are surfaces.
        const auto resource = runtime->get_current_back_buffer();
        if (resource.handle == 0) return;
        auto *native_resource = reinterpret_cast<IUnknown *>(
            static_cast<std::uintptr_t>(resource.handle));
        IDirect3DSurface9 *surface = nullptr;
        const HRESULT queried = native_resource->QueryInterface(IID_IDirect3DSurface9,
            reinterpret_cast<void **>(&surface));
        if (FAILED(queried) || !surface) return;
        // The callback borrows the device; QI owns only this transient surface ref.
        // The pinned D3D9 swapchain wraps present_effect_runtime (including this
        // callback) in its own BeginScene/EndScene. Never nest scene calls.
        const HRESULT rendered = state.renderer.render(device, surface, state.config, true);
        surface->Release();
        if (FAILED(rendered) && !state.error_reported) {
            char text[180];
            std::snprintf(text, sizeof(text),
                "NFSUC Native: render skipped/failed, HRESULT=0x%08lX; inspect native DX9 support. Further failures suppressed.",
                static_cast<unsigned long>(rendered));
            log_warning(text);
            state.error_reported = true;
        }
    } catch (...) {
        log_warning("NFSUC Native: exception in present callback; no exception propagated to game.");
    }
}

void unregister_callbacks() noexcept {
    reshade::unregister_event<reshade::addon_event::destroy_pipeline>(on_destroy_pipeline);
    reshade::unregister_event<reshade::addon_event::init_pipeline>(on_init_pipeline);
    reshade::unregister_event<reshade::addon_event::reshade_present>(on_reshade_present);
    reshade::unregister_event<reshade::addon_event::destroy_device>(on_destroy_device);
    reshade::unregister_event<reshade::addon_event::destroy_swapchain>(on_destroy_swapchain);
    reshade::unregister_event<reshade::addon_event::destroy_effect_runtime>(on_destroy_effect_runtime);
    reshade::unregister_event<reshade::addon_event::init_effect_runtime>(on_init_effect_runtime);
}
} // namespace

// ReShade invokes these lifecycle exports. No DllMain file I/O or hook setup.
extern "C" __declspec(dllexport) bool AddonInit(HMODULE addon_module, HMODULE reshade_module) {
    try {
        if (!is_undercover_process()) return false;
        const auto path = module_path(addon_module);
        if (path.empty()) return false;
        config_path = path.parent_path() / L"NFSUCNative.ini";
        if (!reshade::register_addon(addon_module, reshade_module)) return false;
        registered = true;
        // AddonInit is the SDK lifecycle entry point, not DllMain. Read once here
        // so passive shader observation also sees pipelines created before a runtime.
        addon_config = load_config();
        if (addon_config.observe_shaders)
            shader_registry = std::make_unique<nfsuc::ShaderRegistry>();
        reshade::register_event<reshade::addon_event::init_pipeline>(on_init_pipeline);
        reshade::register_event<reshade::addon_event::destroy_pipeline>(on_destroy_pipeline);
        reshade::register_event<reshade::addon_event::init_effect_runtime>(on_init_effect_runtime);
        reshade::register_event<reshade::addon_event::destroy_effect_runtime>(on_destroy_effect_runtime);
        reshade::register_event<reshade::addon_event::destroy_swapchain>(on_destroy_swapchain);
        reshade::register_event<reshade::addon_event::destroy_device>(on_destroy_device);
        reshade::register_event<reshade::addon_event::reshade_present>(on_reshade_present);
        log_info("NFSUC Native: official ReShade SDK API 20 bridge loaded; only nfs.exe + D3D9 accepted; config defaults disabled.");
        return true;
    } catch (...) {
        if (registered) {
            unregister_callbacks();
            reshade::unregister_addon(addon_module, reshade_module);
            registered = false;
        }
        return false;
    }
}

extern "C" __declspec(dllexport) void AddonUninit(HMODULE addon_module, HMODULE reshade_module) noexcept {
    if (!registered) return;
    unregister_callbacks();
    try {
        std::lock_guard<std::mutex> lock(state_mutex);
        for (const auto &entry : runtimes) entry.second->renderer.release();
        runtimes.clear();
        report_shader_registry();
        {
            std::lock_guard<std::mutex> shader_lock(shader_mutex);
            shader_registry.reset();
        }
    } catch (...) {
        log_warning("NFSUC Native: exception during add-on cleanup; SDK will still be unregistered.");
    }
    reshade::unregister_addon(addon_module, reshade_module);
    registered = false;
}
