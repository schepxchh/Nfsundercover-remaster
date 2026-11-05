// SPDX-License-Identifier: MIT
#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <mutex>
#include <vector>

namespace nfsuc {

enum class ShaderStage { pixel, vertex };
enum class ObserveResult { added, repeated, invalid, capacity };

struct ShaderRecord {
    ShaderStage stage = ShaderStage::pixel;
    std::uint64_t hash = 0;
    std::size_t bytecode_size = 0;
    std::uint32_t version_token = 0;
    std::uint64_t observations = 0;
};

// Read-only observation metadata. No shader bytecode is retained or exported.
// FNV-1a-64 is a NONCRYPTOGRAPHIC grouping key, not an executable compatibility
// fingerprint or semantic shader identifier. Even stage+size+hash can collide;
// repeated therefore means a repeated grouping key, not proven byte equality.
//
// The caller must supply a readable, immutable byte span for the duration of
// observe(). This interface validates size and framing, not pointer readability,
// shader instructions, semantic validity, driver acceptance, or game purpose.
// An unaligned data pointer is supported; the byte length must be DWORD-aligned.
class ShaderRegistry {
public:
    static constexpr std::size_t default_capacity = 256;
    static constexpr std::size_t max_bytecode_size = 1024 * 1024;

    explicit ShaderRegistry(std::size_t max_capacity = default_capacity,
                            std::size_t max_bytecode_bytes = max_bytecode_size)
        : capacity_(max_capacity),
          bytecode_limit_(std::min(max_bytecode_bytes, max_bytecode_size)) {}

    ObserveResult observe(ShaderStage stage, const void* bytecode, std::size_t size) {
        if (!bytecode || size < 8 || size % 4 != 0 || size > bytecode_limit_)
            return ObserveResult::invalid;
        const auto* bytes = static_cast<const unsigned char*>(bytecode);
        const std::uint32_t version = read_u32_le(bytes);
        const bool pixel = stage == ShaderStage::pixel
            && (version == 0xffff0200u || version == 0xffff0300u);
        const bool vertex = stage == ShaderStage::vertex
            && (version == 0xfffe0200u || version == 0xfffe0300u);
        if ((!pixel && !vertex) || read_u32_le(bytes + size - 4) != 0x0000ffffu)
            return ObserveResult::invalid;

        std::uint64_t hash = 14695981039346656037ull;
        for (std::size_t i = 0; i < size; ++i) {
            hash ^= bytes[i];
            hash *= 1099511628211ull; // Unsigned wraparound defines FNV-1a-64.
        }

        const std::lock_guard<std::mutex> lock(mutex_);
        for (auto& record : records_) {
            if (record.stage == stage && record.bytecode_size == size && record.hash == hash) {
                if (record.observations != std::numeric_limits<std::uint64_t>::max())
                    ++record.observations;
                return ObserveResult::repeated;
            }
        }
        if (records_.size() >= capacity_) return ObserveResult::capacity;
        records_.push_back({stage, hash, size, version, 1});
        return ObserveResult::added;
    }

    // A coherent copy in first-observed insertion order; callers cannot mutate
    // registry state through it. Concurrent observe/snapshot calls are serialized.
    std::vector<ShaderRecord> snapshot() const {
        const std::lock_guard<std::mutex> lock(mutex_);
        return records_;
    }

private:
    static std::uint32_t read_u32_le(const unsigned char* bytes) noexcept {
        return static_cast<std::uint32_t>(bytes[0])
            | (static_cast<std::uint32_t>(bytes[1]) << 8)
            | (static_cast<std::uint32_t>(bytes[2]) << 16)
            | (static_cast<std::uint32_t>(bytes[3]) << 24);
    }

    const std::size_t capacity_;
    const std::size_t bytecode_limit_;
    mutable std::mutex mutex_;
    std::vector<ShaderRecord> records_;
};

} // namespace nfsuc
