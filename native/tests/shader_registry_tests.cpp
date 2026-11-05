// SPDX-License-Identifier: MIT
#include "nfsuc/shader_registry.hpp"

#include <atomic>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {
using nfsuc::ObserveResult;
using nfsuc::ShaderRegistry;
using nfsuc::ShaderStage;

void check(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

std::vector<unsigned char> shader(std::uint32_t version, std::uint32_t body = 0) {
    std::vector<unsigned char> result;
    for (const auto word : {version, body, std::uint32_t{0x0000ffffu}})
        for (unsigned shift = 0; shift < 32; shift += 8)
            result.push_back(static_cast<unsigned char>(word >> shift));
    return result;
}

void versions_and_framing() {
    ShaderRegistry registry;
    for (const std::uint32_t version : {0xffff0200u, 0xffff0300u, 0xfffe0200u, 0xfffe0300u}) {
        const auto stage = version >> 16 == 0xffffu ? ShaderStage::pixel : ShaderStage::vertex;
        auto bytes = shader(version);
        check(registry.observe(stage, bytes.data(), bytes.size()) == ObserveResult::added,
              "PS/VS 2.0 and 3.0 should be accepted");
        const auto wrong = stage == ShaderStage::pixel ? ShaderStage::vertex : ShaderStage::pixel;
        check(registry.observe(wrong, bytes.data(), bytes.size()) == ObserveResult::invalid,
              "shader stage/version mismatch accepted");
    }
    for (const std::uint32_t version : {0xffff0104u, 0xffff0201u, 0xffff0400u, 0xfffe0101u, 0u}) {
        const auto bytes = shader(version);
        check(registry.observe(ShaderStage::pixel, bytes.data(), bytes.size()) == ObserveResult::invalid,
              "unsupported version accepted");
    }
    const auto valid = shader(0xffff0300u);
    check(registry.observe(static_cast<ShaderStage>(37), valid.data(), valid.size()) == ObserveResult::invalid,
          "unknown stage accepted");
    check(registry.observe(ShaderStage::pixel, nullptr, valid.size()) == ObserveResult::invalid,
          "null bytecode accepted");
    for (const auto size : {std::size_t{0}, std::size_t{4}, std::size_t{7}, std::size_t{9}})
        check(registry.observe(ShaderStage::pixel, valid.data(), size) == ObserveResult::invalid,
              "invalid byte length accepted");
    auto broken = valid;
    broken.back() = 1;
    check(registry.observe(ShaderStage::pixel, broken.data(), broken.size()) == ObserveResult::invalid,
          "invalid END token accepted");
    check(registry.snapshot().size() == 4, "invalid input changed registry");
}

void hash_metadata_and_copy() {
    // Version + END only: framing observer deliberately does not parse instructions.
    const unsigned char bytes[] = {0x00, 0x02, 0xff, 0xff, 0xff, 0xff, 0x00, 0x00};
    ShaderRegistry registry;
    check(registry.observe(ShaderStage::pixel, bytes, sizeof(bytes)) == ObserveResult::added, "minimal framing rejected");
    check(registry.observe(ShaderStage::pixel, bytes, sizeof(bytes)) == ObserveResult::repeated, "repeat not grouped");
    auto copy = registry.snapshot();
    check(copy.size() == 1 && copy[0].hash == 0xe1ba805fd4e051cbull, "FNV-1a-64 known vector mismatch");
    check(copy[0].stage == ShaderStage::pixel && copy[0].version_token == 0xffff0200u,
          "stage/version metadata mismatch");
    check(copy[0].bytecode_size == sizeof(bytes) && copy[0].observations == 2, "size/count metadata mismatch");
    copy[0].observations = 900;
    copy.clear();
    check(registry.snapshot()[0].observations == 2, "snapshot aliases live metadata");

    auto source = shader(0xffff0300u, 0xdeadbeefu);
    check(registry.observe(ShaderStage::pixel, source.data(), source.size()) == ObserveResult::added,
          "observer improperly required instruction semantics");
    const auto prior = registry.snapshot()[1].hash;
    source.assign(source.size(), 0);
    check(registry.snapshot()[1].hash == prior, "registry retained or reread source bytecode");
}

void bounds_and_order() {
    ShaderRegistry registry(2);
    const auto a = shader(0xffff0300u, 1);
    const auto b = shader(0xffff0300u, 2);
    const auto c = shader(0xffff0300u, 3);
    check(registry.observe(ShaderStage::pixel, a.data(), a.size()) == ObserveResult::added, "first add failed");
    const auto first_hash = registry.snapshot()[0].hash;
    check(registry.observe(ShaderStage::pixel, b.data(), b.size()) == ObserveResult::added, "second add failed");
    const auto second_hash = registry.snapshot()[1].hash;
    check(registry.observe(ShaderStage::pixel, c.data(), c.size()) == ObserveResult::capacity, "capacity ignored");
    check(registry.observe(ShaderStage::pixel, a.data(), a.size()) == ObserveResult::repeated,
          "repeat at capacity should be counted");
    const auto copy = registry.snapshot();
    check(copy.size() == 2 && copy[0].hash == first_hash && copy[1].hash == second_hash,
          "stable insertion order changed or capacity exceeded");
    ShaderRegistry empty(0);
    check(empty.observe(ShaderStage::pixel, a.data(), a.size()) == ObserveResult::capacity, "zero capacity ignored");
    check(empty.snapshot().empty(), "zero-capacity registry stored record");

    ShaderRegistry limited(4, 8);
    check(limited.observe(ShaderStage::pixel, a.data(), a.size()) == ObserveResult::invalid, "custom byte limit ignored");
    ShaderRegistry none(4, 0);
    check(none.observe(ShaderStage::pixel, a.data(), a.size()) == ObserveResult::invalid, "zero byte limit ignored");

    std::vector<unsigned char> maximum(ShaderRegistry::max_bytecode_size, 0);
    maximum[0] = 0; maximum[1] = 3; maximum[2] = 0xff; maximum[3] = 0xff;
    maximum[maximum.size() - 4] = 0xff; maximum[maximum.size() - 3] = 0xff;
    ShaderRegistry bounded(2, ShaderRegistry::max_bytecode_size + 4);
    check(bounded.observe(ShaderStage::pixel, maximum.data(), maximum.size()) == ObserveResult::added,
          "1 MiB framing boundary rejected");
    maximum.insert(maximum.end(), {0xff, 0xff, 0, 0});
    check(bounded.observe(ShaderStage::pixel, maximum.data(), maximum.size()) == ObserveResult::invalid,
          "hard 1 MiB ceiling ignored");

    ShaderRegistry defaults;
    for (std::uint32_t i = 0; i < ShaderRegistry::default_capacity; ++i) {
        const auto current = shader(0xffff0300u, i);
        check(defaults.observe(ShaderStage::pixel, current.data(), current.size()) == ObserveResult::added,
              "default capacity exhausted early");
    }
    const auto extra = shader(0xffff0300u, 0xffffffffu);
    check(defaults.observe(ShaderStage::pixel, extra.data(), extra.size()) == ObserveResult::capacity,
          "default capacity exceeded");
}

void unaligned_read() {
    const auto bytes = shader(0xfffe0300u);
    std::vector<unsigned char> unaligned(bytes.size() + 1, 0);
    std::copy(bytes.begin(), bytes.end(), unaligned.begin() + 1);
    ShaderRegistry registry;
    check(registry.observe(ShaderStage::vertex, unaligned.data() + 1, bytes.size()) == ObserveResult::added,
          "unaligned input address should be read bytewise");
}

void concurrent_observation() {
    ShaderRegistry registry(8);
    constexpr unsigned thread_count = 8, repeats = 4000;
    const auto bytes = shader(0xffff0300u, 0x12345678u);
    std::atomic<unsigned> added{0}, failed{0};
    std::vector<std::thread> threads;
    for (unsigned i = 0; i < thread_count; ++i) {
        threads.emplace_back([&] {
            for (unsigned j = 0; j < repeats; ++j) {
                const auto result = registry.observe(ShaderStage::pixel, bytes.data(), bytes.size());
                if (result == ObserveResult::added) ++added;
                else if (result != ObserveResult::repeated) ++failed;
                if (j % 31 == 0) {
                    auto copy = registry.snapshot();
                    if (copy.size() != 1 || copy[0].observations == 0) ++failed;
                }
            }
        });
    }
    for (auto& thread : threads) thread.join();
    const auto result = registry.snapshot();
    check(added == 1 && failed == 0, "concurrent first-add or snapshot invariant broken");
    check(result.size() == 1 && result[0].observations == thread_count * repeats,
          "concurrent observations lost");
}
}

int main() {
    try {
        versions_and_framing();
        hash_metadata_and_copy();
        bounds_and_order();
        unaligned_read();
        concurrent_observation();
        std::cout << "shader_registry_tests: 5 cases passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "shader_registry_tests: " << error.what() << '\n';
        return 1;
    }
}
