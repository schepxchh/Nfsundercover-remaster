// SPDX-License-Identifier: MIT
// Standalone tests: checks stay active under NDEBUG / Release builds.
#include "nfsuc/core.hpp"

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

namespace {
int checks = 0;
void check(bool condition, const char* message) {
    ++checks;
    if (!condition) {
        std::cerr << "FAILED: " << message << '\n';
        std::exit(EXIT_FAILURE);
    }
}
bool close(float a, float b, float epsilon = 0.000003f) { return std::fabs(a - b) <= epsilon; }
bool bounded(nfsuc::Rgb c) {
    return std::isfinite(c.r) && std::isfinite(c.g) && std::isfinite(c.b)
        && c.r >= 0 && c.r <= 1 && c.g >= 0 && c.g <= 1 && c.b >= 0 && c.b <= 1;
}
void config_tests() {
    const auto defaults = nfsuc::parse_config("");
    check(defaults.ok() && !defaults.value.enabled && !defaults.value.observe_shaders, "default native processing is disabled");
    const auto parsed = nfsuc::parse_config(
        "# visual only\r\n Enabled = 1\r\n ObserveShaders=1\n"
        "Exposure=-.5\nContrast=.2\nSaturation=1.15\nWarmth=-0.5\nShoulder=5e-1\nStrength=0\n; done\n");
    check(parsed.ok(), "valid bounded config parses with classic decimal/exponent syntax");
    check(parsed.value.enabled && parsed.value.observe_shaders, "explicit switches parsed");
    check(parsed.value.grade.exposure == -0.5f && parsed.value.grade.shoulder == 0.5f, "grade values applied");
    check(nfsuc::valid_grade(parsed.value.grade), "parsed values satisfy grade contract");
    for (const auto* invalid : {
        "SimRate=120", "FPSLimit=144", "Handling=1", "AI=0", "EngineShadows=1", "EnableLOD=1",
        "enabled=1", "Enabled=true", "Enabled=-1", "Enabled=2", "Enabled=1 # inline",
        "Enabled=1\nEnabled=0", "Exposure=nan", "Exposure=inf", "Exposure=-inf", "Exposure=1e30",
        "Exposure=1e999", "Exposure=0x1", "Exposure=0.50001", "Exposure=-0.50001", "Contrast=-.001",
        "Contrast=.20001", "Saturation=.7999", "Saturation=1.1501", "Warmth=.5001",
        "Shoulder=-.001", "Shoulder=.5001", "Strength=-.001", "Strength=1.001", "Strength=1f",
        "Exposure=", "Exposure=--.1", "Exposure=1.2.3", "Exposure=1=2", "[Native]", "=1"
    }) {
        const auto rejected = nfsuc::parse_config(std::string("Enabled=1\n") + invalid);
        check(!rejected.ok() && !rejected.value.enabled, "invalid config fails closed");
    }
    const auto oversized = nfsuc::parse_config(std::string(65537, '#'));
    check(!oversized.ok(), "oversized config rejected");
}
void policy_tests() {
    nfsuc::Config config;
    nfsuc::DeviceCaps caps{3, 0, true};
    check(!nfsuc::evaluate_policy(config, caps).native_grade, "grade requires explicit opt-in");
    config.enabled = true;
    check(nfsuc::evaluate_policy(config, caps).native_grade, "PS3 SDR and valid explicit grade allowed");
    caps.pixel_shader_major = 2;
    check(!nfsuc::evaluate_policy(config, caps).native_grade, "PS2 grade denied");
    caps.pixel_shader_major = 3;
    caps.sdr_target = false;
    check(!nfsuc::evaluate_policy(config, caps).native_grade, "unconfirmed/HDR target denied");
    caps.sdr_target = true;
    config.grade.strength = std::numeric_limits<float>::quiet_NaN();
    check(!nfsuc::evaluate_policy(config, caps).native_grade, "nonfinite runtime grade denied");
    config.grade.strength = 1;
    const auto all_confirmed = nfsuc::evaluate_policy(config, caps, {true, true, true, true, true});
    check(!all_confirmed.engine_shadows && !all_confirmed.geometry && !all_confirmed.lod
        && !all_confirmed.reflections && !all_confirmed.particles, "unimplemented engine modules stay disabled even with semantic evidence");
    check(all_confirmed.reasons.size() == 5, "engine blockers reported individually");
}
void graph_tests() {
    const auto grade = nfsuc::compile_graph(nfsuc::make_grade_graph());
    check(grade.ok() && grade.order == std::vector<std::size_t>{0}, "real grade graph compiles");
    nfsuc::Graph stable{
        {{"a", false}, {"b", false}},
        {{"consume-a", {"a"}, {}}, {"consume-b", {"b"}, {}},
         {"produce-a", {}, {"a"}}, {"produce-b", {}, {"b"}}}
    };
    const auto sorted = nfsuc::compile_graph(stable);
    check(sorted.ok() && sorted.order == std::vector<std::size_t>({2, 0, 3, 1}), "topological order is stable by lowest available original index");
    const auto invalid = [](const nfsuc::Graph& graph) {
        const auto result = nfsuc::compile_graph(graph);
        check(!result.ok() && result.order.empty(), "invalid graph cannot yield an executable order");
    };
    invalid({{{"a", false}}, {{"consumer", {"a"}, {}}}}); // missing producer
    invalid({{{"a", false}, {"b", false}}, {{"a", {"b"}, {"a"}}, {"b", {"a"}, {"b"}}}}); // cycle
    invalid({{{"a", false}}, {{"feedback", {"a"}, {"a"}}}});
    invalid({{{"a", false}}, {{"a", {}, {"a"}}, {"b", {}, {"a"}}}}); // writers
    invalid({{{"a", true}}, {{"write-import", {}, {"a"}}}});
    invalid({{}, {{"read-unknown", {"x"}, {}}}});
    invalid({{}, {{"write-unknown", {}, {"x"}}}});
    invalid({{{"a", true}, {"a", false}}, {}});
    invalid({{}, {{"same", {}, {}}, {"same", {}, {}}}});
    invalid({{{"a", true}}, {{"repeat-read", {"a", "a"}, {}}}});
    invalid({{{"a", false}}, {{"repeat-write", {}, {"a", "a"}}}});
    invalid({{{"", true}}, {}});
    nfsuc::Graph too_large;
    too_large.passes.resize(129);
    invalid(too_large);
    check(nfsuc::compile_graph({}).ok(), "empty graph represents bypass");
}
void grade_tests() {
    nfsuc::NativeGrade identity;
    identity.exposure = 0;
    identity.contrast = 0;
    identity.saturation = 1;
    identity.warmth = 0;
    identity.shoulder = 0;
    for (const auto input : {nfsuc::Rgb{0, 0, 0}, nfsuc::Rgb{1, 1, 1}, nfsuc::Rgb{0.001f, 0.02f, 0.1f},
                            nfsuc::Rgb{0.21f, 0.62f, 0.91f}, nfsuc::Rgb{1, 0, 0}}) {
        const auto output = nfsuc::grade_sdr(input, identity);
        check(close(input.r, output.r) && close(input.g, output.g) && close(input.b, output.b), "neutral grade preserves SDR colors including dark and white endpoints");
    }
    auto neutral_strength = nfsuc::NativeGrade{};
    neutral_strength.strength = 0;
    const auto source = nfsuc::Rgb{.2f, .3f, .4f};
    const auto off = nfsuc::grade_sdr(source, neutral_strength);
    check(off.r == source.r && off.g == source.g && off.b == source.b, "zero strength exactly bypasses");
    float previous = -1;
    for (int i = 0; i <= 4096; ++i) {
        const auto value = static_cast<float>(i) / 4096.0f;
        const auto output = nfsuc::grade_sdr({value, value, value}, nfsuc::NativeGrade{});
        check(bounded(output), "default grayscale stays finite and in SDR gamut");
        check(output.r + 0.000001f >= previous, "default grade has no tonal reversals");
        previous = output.r;
    }
    for (const auto exposure : {-0.5f, 0.5f}) {
        for (const auto warmth : {-0.5f, 0.5f}) {
            for (const auto saturation : {0.8f, 1.15f}) {
                auto extreme = nfsuc::NativeGrade{};
                extreme.exposure = exposure;
                extreme.contrast = 0.2f;
                extreme.warmth = warmth;
                extreme.saturation = saturation;
                extreme.shoulder = 0.5f;
                for (int r = 0; r <= 8; ++r) for (int g = 0; g <= 8; ++g) for (int b = 0; b <= 8; ++b)
                    check(bounded(nfsuc::grade_sdr({r / 8.0f, g / 8.0f, b / 8.0f}, extreme)), "endpoint parameter combinations preserve finite gamut");
            }
        }
    }
    auto invalid = nfsuc::NativeGrade{};
    invalid.exposure = std::numeric_limits<float>::infinity();
    const auto bypass = nfsuc::grade_sdr(source, invalid);
    check(bypass.r == source.r && bypass.g == source.g && bypass.b == source.b, "invalid grade cannot corrupt rendered color");
    check(bounded(nfsuc::grade_sdr({std::numeric_limits<float>::quiet_NaN(), -2, 4}, identity)), "malformed CPU reference input is bounded");
}
void lifecycle_tests() {
    nfsuc::DeviceLifecycle life;
    check(!life.can_render() && !life.resources_ready(), "uninitialized lifecycle cannot render");
    check(!life.begin_reset() && !life.finish_reset(true), "invalid reset transition denied");
    check(life.device_created() && !life.device_created(), "device creation transitions once");
    check(!life.can_render() && life.resources_ready() && life.can_render(), "GPU resources explicitly required");
    life.record_frame(true);
    life.device_lost();
    life.device_lost();
    check(!life.can_render() && !life.resources_ready(), "loss immediately invalidates owned resources");
    life.record_frame(true);
    check(life.begin_reset() && !life.begin_reset(), "reset begins once and invalidates resources");
    check(life.finish_reset(false) && life.state() == nfsuc::DeviceState::Lost, "failed reset remains lost");
    check(life.begin_reset() && life.finish_reset(true), "reset retry can recover");
    check(!life.can_render(), "successful reset requires resources to be recreated");
    check(life.resources_ready() && life.can_render(), "recreated resources permit render");
    life.record_frame(true);
    check(life.telemetry().generation == 2 && life.telemetry().lost_events == 1
        && life.telemetry().reset_attempts == 2 && life.telemetry().reset_failures == 1,
        "device telemetry tracks generation, one loss and reset outcomes");
    check(life.telemetry().frames_seen == 3 && life.telemetry().frames_graded == 2
        && life.telemetry().frames_bypassed == 1, "frame telemetry never counts rendering while lost");
    life.shutdown();
    check(!life.can_render() && !life.device_created() && !life.begin_reset() && !life.resources_ready(), "shutdown permanently disables lifecycle");
}

}

int main() {
    config_tests();
    policy_tests();
    graph_tests();
    grade_tests();
    lifecycle_tests();
    std::cout << "nfsuc core: " << checks << " checks passed\n";
    return EXIT_SUCCESS;
}
