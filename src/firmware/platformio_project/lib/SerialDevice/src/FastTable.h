#include <Arduino.h>

#define BLOCKSIZE 16
#define BLOCKSAMOUNT 16

/**
 * @brief Fixed-size container block holding a subset of table values.
 *
 * Each block stores BLOCKSIZE elements of type T. Blocks are allocated
 * lazily by FastTable when a key in their range is first written.
 *
 * @tparam T Type of values stored in the table.
 */
template<typename T>
struct TableBlock {
    T items[BLOCKSIZE];

    /**
     * @brief Constructs a block and default-initializes all elements.
     *
     * Each slot is initialized using T(), which requires that T is
     * default-constructible.
     */
    TableBlock() {
        for (int i = 0; i < BLOCKSIZE; ++i) {
            items[i] = T();
        }
    }
};

/**
 * @brief Fast fixed-size lookup table for 8-bit keys (0–255).
 *
 * This class implements a two-level array:
 * - Top level: 16 pointers to TableBlock<T>
 * - Second level: 16 items per block
 *
 * Blocks are allocated on demand, reducing memory usage when the table
 * is sparsely populated. Lookup and insertion are constant time (O(1)).
 *
 * @tparam T Type of values stored in the table.
 */
template<typename T>
class FastTable {
private:
    /// Array of pointers to lazily allocated blocks.
    TableBlock<T>* blocks[BLOCKSAMOUNT] = {nullptr};

public:
    /**
     * @brief Inserts or updates a value associated with a key.
     *
     * If the corresponding block does not exist, it is allocated.
     * The value is then copied into the appropriate slot.
     *
     * @param key 8-bit key (0–255).
     * @param value Value to store (copied into the table).
     */
    void put(uint8_t key, const T& value) {
        uint8_t blockIndex = key >> 4;
        if (blocks[blockIndex] == nullptr) {
            blocks[blockIndex] = new TableBlock<T>();
        }
        uint8_t insideBlockIndex = key & 0x0F;
        blocks[blockIndex]->items[insideBlockIndex] = value;
    }

    /**
     * @brief Retrieves a const pointer to the value associated with a key.
     *
     * @param key 8-bit key (0–255).
     * @return Const pointer to the stored value, or nullptr if the block
     *         for this key has not been allocated.
     */
    const T* get(const uint8_t key) const {
        uint8_t blockIndex = key >> 4;
        if (blocks[blockIndex] == nullptr) {
            return nullptr;
        }
        uint8_t insideBlockIndex = key & 0x0F;
        return &blocks[blockIndex]->items[insideBlockIndex];
    }

    /**
     * @brief Destructor that releases all allocated blocks.
     */
    ~FastTable() {
        for (int i = 0; i < BLOCKSAMOUNT; ++i) {
            delete blocks[i];
        }
    }
};