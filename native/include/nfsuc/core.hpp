// SPDX-License-Identifier: MIT
#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace nfsuc {

struct NativeGrade {
    float exposure = 0.03f;       // [-0.5, 0.5] display-referred EV
    float contrast = 0.035f;      // [0, 0.2]
    float saturation = 1.025f;    // [0.8, 1.15]
    float warmth = 0.06f;        // [-0.5, 0.5]
    float shoulder = 0.15f;      // [0, 0.5]
    float strength = 1.0f;       // [0, 1]
};

struct Config {
    bool enabled = false;
    bool observe_shaders = false;
    NativeGrade grade;
};

struct ConfigParseResult {
    Config value;
    std::vector<std::string> errors;
    bool ok() const noexcept { return errors.empty(); }
};

// Exact keys: Enabled, ObserveShaders, Exposure, Contrast, Saturation, Warmth,
// Shoulder, Strength. Booleans are 0/1. Full-line #/; comments are accepted.
// Any error returns disabled defaults; callers must also check ok().
ConfigParseResult parse_config(std::string_view text);
bool valid_grade(const NativeGrade& grade) noexcept;

struct Rgb { float r, g, b; };
// Foundation shader equations with ShadowLift=0; SDR approximation, not HDR
// reconstruction. Invalid grade parameters return a clamped input unchanged.
Rgb grade_sdr(Rgb source, const NativeGrade& grade) noexcept;

struct DeviceCaps {
    unsigned pixel_shader_major = 0;
    unsigned pixel_shader_minor = 0;
    bool sdr_target = false;
};

struct SemanticResources {
    bool confirmed_shadow_maps = false;
    bool confirmed_geometry = false;
    bool confirmed_lod = false;
    bool confirmed_reflections = false;
    bool confirmed_particles = false;
};

struct Capabilities {
    bool native_grade = false;
    bool engine_shadows = false;
    bool geometry = false;
    bool lod = false;
    bool reflections = false;
    bool particles = false;
    std::vector<std::string> reasons;
};

// Engine modules remain disabled even with confirmed semantics: no engine
// implementation ships here. Semantic evidence is a prerequisite, not a patch.
Capabilities evaluate_policy(const Config&, const DeviceCaps&, const SemanticResources& = {});

// A small SSA-style render graph: one producer per internal resource; imported
// external resources are read-only. No in-place feedback or implicit ordering.
struct ResourceDesc { std::string name; bool external = false; };
struct PassDesc {
    std::string name;
    std::vector<std::string> reads;
    std::vector<std::string> writes;
};
struct Graph {
    std::vector<ResourceDesc> resources;
    std::vector<PassDesc> passes;
};
struct GraphResult {
    std::vector<std::size_t> order;
    std::vector<std::string> errors;
    bool ok() const noexcept { return errors.empty(); }
};
GraphResult compile_graph(const Graph& graph);
Graph make_grade_graph();

enum class DeviceState { Uninitialized, Ready, Lost, Resetting, Stopped };
struct Telemetry {
    std::uint64_t frames_seen = 0;
    std::uint64_t frames_graded = 0;
    std::uint64_t frames_bypassed = 0;
    std::uint64_t lost_events = 0;
    std::uint64_t reset_attempts = 0;
    std::uint64_t reset_failures = 0;
    std::uint64_t generation = 0;
};

// Models ownership validity, never owns D3D objects. The DX9 adapter must release
// default-pool resources BEFORE Reset and mark resources ready after recreation.
class DeviceLifecycle {
public:
    bool device_created() noexcept;
    void device_lost() noexcept;
    bool begin_reset() noexcept;
    bool finish_reset(bool success) noexcept;
    bool resources_ready() noexcept;
    void shutdown() noexcept;
    void record_frame(bool grade_executed) noexcept;
    bool can_render() const noexcept;
    DeviceState state() const noexcept { return state_; }
    const Telemetry& telemetry() const noexcept { return telemetry_; }
private:
    DeviceState state_ = DeviceState::Uninitialized;
    bool resources_valid_ = false;
    Telemetry telemetry_;
};

} // namespace nfsuc
