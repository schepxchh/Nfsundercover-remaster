// SPDX-License-Identifier: MIT
#include "nfsuc/core.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <functional>
#include <iomanip>
#include <limits>
#include <locale>
#include <map>
#include <queue>
#include <set>
#include <sstream>
#include <utility>

namespace nfsuc {
namespace {
std::string_view trim(std::string_view value) {
    constexpr std::string_view whitespace = " \t\r\n";
    const auto first = value.find_first_not_of(whitespace);
    if (first == std::string_view::npos) return {};
    return value.substr(first, value.find_last_not_of(whitespace) - first + 1);
}
bool bounded(float value, float low, float high) noexcept {
    return std::isfinite(value) && value >= low && value <= high;
}
float saturate(float value) noexcept {
    return std::isfinite(value) ? std::max(0.0f, std::min(1.0f, value)) : 0.0f;
}
float luma(Rgb c) noexcept { return c.r * 0.2126f + c.g * 0.7152f + c.b * 0.0722f; }
Rgb scale(Rgb c, float amount) noexcept { return {c.r * amount, c.g * amount, c.b * amount}; }
void increment(std::uint64_t& value) noexcept {
    if (value != std::numeric_limits<std::uint64_t>::max()) ++value;
}
bool parse_float(std::string_view text, float& value) {
    // Locale-independent decimal numbers only, not NaN/Inf, hex, suffixes or
    // trailing garbage. Exponents are accepted and then bounded below.
    if (text.empty() || text.find_first_not_of("0123456789+-.eE") != std::string_view::npos) return false;
    std::istringstream stream{std::string(text)};
    stream.imbue(std::locale::classic());
    stream >> std::noskipws >> value;
    return stream && stream.eof() && std::isfinite(value);
}
}

bool valid_grade(const NativeGrade& g) noexcept {
    return bounded(g.exposure, -0.5f, 0.5f) && bounded(g.contrast, 0.0f, 0.2f)
        && bounded(g.saturation, 0.8f, 1.15f) && bounded(g.warmth, -0.5f, 0.5f)
        && bounded(g.shoulder, 0.0f, 0.5f) && bounded(g.strength, 0.0f, 1.0f);
}

ConfigParseResult parse_config(std::string_view text) {
    ConfigParseResult result;
    Config candidate;
    if (text.size() > 64 * 1024) {
        result.errors.emplace_back("Configuration exceeds 64 KiB");
        return result;
    }
    std::set<std::string> keys;
    std::size_t line_number = 0;
    while (!text.empty()) {
        ++line_number;
        const auto end = text.find('\n');
        auto line = trim(text.substr(0, end));
        text = end == std::string_view::npos ? std::string_view{} : text.substr(end + 1);
        if (line.empty() || line.front() == '#' || line.front() == ';') continue;
        const auto fail = [&](const std::string& reason) {
            result.errors.push_back("Line " + std::to_string(line_number) + ": " + reason);
        };
        const auto equals = line.find('=');
        if (equals == std::string_view::npos || line.find('=', equals + 1) != std::string_view::npos) {
            fail("expected exactly one key=value assignment");
            continue;
        }
        const auto key = std::string(trim(line.substr(0, equals)));
        const auto value = trim(line.substr(equals + 1));
        if (!keys.insert(key).second) {
            fail("duplicate key: " + key);
            continue;
        }
        if (key == "Enabled" || key == "ObserveShaders") {
            if (value != "0" && value != "1") {
                fail("boolean must be 0 or 1: " + key);
                continue;
            }
            if (key == "Enabled") candidate.enabled = value == "1";
            else candidate.observe_shaders = value == "1";
            continue;
        }
        float* target = nullptr;
        float low = 0.0f, high = 0.0f;
        if (key == "Exposure") { target = &candidate.grade.exposure; low = -0.5f; high = 0.5f; }
        else if (key == "Contrast") { target = &candidate.grade.contrast; high = 0.2f; }
        else if (key == "Saturation") { target = &candidate.grade.saturation; low = 0.8f; high = 1.15f; }
        else if (key == "Warmth") { target = &candidate.grade.warmth; low = -0.5f; high = 0.5f; }
        else if (key == "Shoulder") { target = &candidate.grade.shoulder; high = 0.5f; }
        else if (key == "Strength") { target = &candidate.grade.strength; high = 1.0f; }
        else {
            fail("unknown or prohibited key: " + key);
            continue;
        }
        float number = 0.0f;
        if (!parse_float(value, number) || !bounded(number, low, high)) {
            fail("invalid or out-of-range value: " + key);
            continue;
        }
        *target = number;
    }
    if (result.ok()) result.value = candidate;
    return result;
}

Rgb grade_sdr(Rgb source, const NativeGrade& g) noexcept {
    source = {saturate(source.r), saturate(source.g), saturate(source.b)};
    if (!valid_grade(g) || g.strength == 0.0f) return source;
    Rgb c{std::pow(source.r, 2.2f), std::pow(source.g, 2.2f), std::pow(source.b, 2.2f)};
    c = scale(c, std::exp2(g.exposure));
    c = scale(c, std::pow((luma(c) + 0.02f) / 0.20f, g.contrast));
    c.r *= 1.0f + 0.08f * g.warmth;
    c.b *= 1.0f - 0.08f * g.warmth;
    const auto y = luma(c);
    c = {std::max(0.0f, y + (c.r - y) * g.saturation),
         std::max(0.0f, y + (c.g - y) * g.saturation),
         std::max(0.0f, y + (c.b - y) * g.saturation)};
    const auto peak = std::max(c.r, std::max(c.g, c.b));
    const auto t = std::max(peak - 0.65f, 0.0f) / 0.35f;
    const auto compressed = 0.65f + 0.35f * t / (1.0f + g.shoulder * t);
    c = scale(c, 1.0f - (peak - std::min(peak, compressed)) / std::max(peak, 0.000001f));
    c = scale(c, 1.0f / std::max(1.0f, std::max(c.r, std::max(c.g, c.b))));
    const Rgb encoded{std::pow(saturate(c.r), 1.0f / 2.2f),
                      std::pow(saturate(c.g), 1.0f / 2.2f),
                      std::pow(saturate(c.b), 1.0f / 2.2f)};
    return {source.r + (encoded.r - source.r) * g.strength,
            source.g + (encoded.g - source.g) * g.strength,
            source.b + (encoded.b - source.b) * g.strength};
}

Capabilities evaluate_policy(const Config& config, const DeviceCaps& caps, const SemanticResources& semantic) {
    Capabilities result;
    if (!config.enabled) result.reasons.emplace_back("Native grade disabled by explicit configuration");
    if (caps.pixel_shader_major < 3) result.reasons.emplace_back("Native grade requires pixel shader 3.0");
    if (!caps.sdr_target) result.reasons.emplace_back("Native grade requires a confirmed SDR target");
    if (!valid_grade(config.grade)) result.reasons.emplace_back("Native grade parameters are invalid");
    result.native_grade = config.enabled && caps.pixel_shader_major >= 3 && caps.sdr_target && valid_grade(config.grade);
    const auto blocked = [&](const char* name, bool confirmed) {
        result.reasons.push_back(std::string(name) + (confirmed
            ? ": semantic resources confirmed; engine processing not implemented"
            : ": disabled; semantic resources unconfirmed and engine processing not implemented"));
    };
    blocked("Shadows", semantic.confirmed_shadow_maps);
    blocked("Geometry", semantic.confirmed_geometry);
    blocked("LOD", semantic.confirmed_lod);
    blocked("Reflections", semantic.confirmed_reflections);
    blocked("Particles", semantic.confirmed_particles);
    return result;
}

GraphResult compile_graph(const Graph& graph) {
    GraphResult result;
    if (graph.resources.size() > 128 || graph.passes.size() > 128) {
        result.errors.emplace_back("Render graph exceeds 128 resources or passes");
        return result;
    }
    std::map<std::string, bool> resources;
    std::set<std::string> pass_names;
    std::map<std::string, std::size_t> producers;
    for (const auto& resource : graph.resources) {
        if (resource.name.empty() || !resources.emplace(resource.name, resource.external).second)
            result.errors.emplace_back("Empty or duplicate resource: " + resource.name);
    }
    for (std::size_t i = 0; i < graph.passes.size(); ++i) {
        const auto& pass = graph.passes[i];
        if (pass.name.empty() || !pass_names.insert(pass.name).second)
            result.errors.emplace_back("Empty or duplicate pass: " + pass.name);
        std::set<std::string> reads;
        for (const auto& name : pass.reads) {
            if (!reads.insert(name).second) result.errors.emplace_back("Duplicate read in " + pass.name + ": " + name);
            if (!resources.count(name)) result.errors.emplace_back("Undeclared read in " + pass.name + ": " + name);
        }
        std::set<std::string> writes;
        for (const auto& name : pass.writes) {
            if (!writes.insert(name).second) result.errors.emplace_back("Duplicate write in " + pass.name + ": " + name);
            const auto resource = resources.find(name);
            if (resource == resources.end()) result.errors.emplace_back("Undeclared write in " + pass.name + ": " + name);
            else if (resource->second) result.errors.emplace_back("External resource is read-only: " + name);
            if (reads.count(name)) result.errors.emplace_back("Read/write feedback in " + pass.name + ": " + name);
            if (!producers.emplace(name, i).second) result.errors.emplace_back("Multiple producers for resource: " + name);
        }
    }
    std::vector<std::set<std::size_t>> outgoing(graph.passes.size());
    std::vector<std::size_t> indegree(graph.passes.size(), 0);
    for (std::size_t i = 0; i < graph.passes.size(); ++i) {
        for (const auto& name : graph.passes[i].reads) {
            const auto resource = resources.find(name);
            if (resource == resources.end() || resource->second) continue;
            const auto producer = producers.find(name);
            if (producer == producers.end()) result.errors.emplace_back("Missing producer for resource: " + name);
            else if (outgoing[producer->second].insert(i).second) ++indegree[i];
        }
    }
    if (!result.ok()) return result;
    std::priority_queue<std::size_t, std::vector<std::size_t>, std::greater<std::size_t>> ready;
    for (std::size_t i = 0; i < indegree.size(); ++i) if (indegree[i] == 0) ready.push(i);
    while (!ready.empty()) {
        const auto index = ready.top();
        ready.pop();
        result.order.push_back(index);
        for (const auto child : outgoing[index]) if (--indegree[child] == 0) ready.push(child);
    }
    if (result.order.size() != graph.passes.size()) {
        result.errors.emplace_back("Render graph contains a dependency cycle");
        result.order.clear();
    }
    return result;
}

Graph make_grade_graph() {
    return {{{"SceneColor", true}, {"GradedColor", false}},
            {{"NativeGrade", {"SceneColor"}, {"GradedColor"}}}};
}

bool DeviceLifecycle::device_created() noexcept {
    if (state_ != DeviceState::Uninitialized) return false;
    state_ = DeviceState::Ready;
    resources_valid_ = false;
    increment(telemetry_.generation);
    return true;
}
void DeviceLifecycle::device_lost() noexcept {
    if (state_ == DeviceState::Uninitialized || state_ == DeviceState::Stopped) return;
    if (state_ != DeviceState::Lost) increment(telemetry_.lost_events);
    state_ = DeviceState::Lost;
    resources_valid_ = false;
}
bool DeviceLifecycle::begin_reset() noexcept {
    if (state_ != DeviceState::Ready && state_ != DeviceState::Lost) return false;
    state_ = DeviceState::Resetting;
    resources_valid_ = false;
    increment(telemetry_.reset_attempts);
    return true;
}
bool DeviceLifecycle::finish_reset(bool success) noexcept {
    if (state_ != DeviceState::Resetting) return false;
    state_ = success ? DeviceState::Ready : DeviceState::Lost;
    resources_valid_ = false;
    if (success) increment(telemetry_.generation);
    else increment(telemetry_.reset_failures);
    return true;
}
bool DeviceLifecycle::resources_ready() noexcept {
    if (state_ != DeviceState::Ready) return false;
    resources_valid_ = true;
    return true;
}
void DeviceLifecycle::shutdown() noexcept {
    resources_valid_ = false;
    state_ = DeviceState::Stopped;
}
bool DeviceLifecycle::can_render() const noexcept { return state_ == DeviceState::Ready && resources_valid_; }
void DeviceLifecycle::record_frame(bool grade_executed) noexcept {
    increment(telemetry_.frames_seen);
    if (grade_executed && can_render()) increment(telemetry_.frames_graded);
    else increment(telemetry_.frames_bypassed);
}

} // namespace nfsuc
