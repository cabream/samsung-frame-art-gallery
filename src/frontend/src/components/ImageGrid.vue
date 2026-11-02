<template>
  <div class="image-grid-container">
    <div class="grid-header">
      <div class="select-controls">
        <label class="select-all">
          <input
            type="checkbox"
            :checked="allSelected"
            @change="$emit('select-all', $event.target.checked)"
          />
          Select All ({{ selectedCount }}/{{ displayTotal }})
        </label>
        <button
          v-if="selectedCount > 0"
          class="deselect-btn"
          @click="$emit('select-all', false)"
        >
          Deselect All
        </button>
      </div>
      <slot name="header-actions"></slot>
    </div>

    <div v-if="loading && images.length === 0" class="loading">Loading...</div>

    <div v-else-if="!loading && images.length === 0" class="empty">
      No images found
    </div>

    <div v-else ref="gridRef" class="grid-container" @scroll="onScroll">
      <MasonryWall
        :items="visibleImages"
        :column-width="180"
        :gap="16"
        :ssr-columns="4"
        :scroll-container="gridRef"
      >
        <template #default="{ item }">
          <ImageCard
            :image="item"
            :selected="selectedIds.has(item._id || item.path || item.object_id || item.content_id)"
            :is-current="currentId === (item.content_id)"
            :is-local="isLocal"
            @toggle="$emit('toggle', item)"
            @preview="$emit('preview', item)"
          />
        </template>
      </MasonryWall>
      <div v-if="hasMore" ref="sentinelRef" class="load-more-sentinel">
        <div v-if="loadingMore" class="loading-spinner">
          <div class="spinner"></div>
          <span>Loading more...</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onUnmounted, provide, nextTick } from 'vue'
import MasonryWall from '@yeger/vue-masonry-wall'
import ImageCard from './ImageCard.vue'

const BATCH_SIZE = 24

const props = defineProps({
  images: { type: Array, default: () => [] },
  selectedIds: { type: Set, default: () => new Set() },
  currentId: { type: String, default: null },
  loading: { type: Boolean, default: false },
  loadingMore: { type: Boolean, default: false },
  isLocal: { type: Boolean, default: true },
  hasMoreExternal: { type: Boolean, default: false },
  totalCount: { type: Number, default: null }
})

const emit = defineEmits(['toggle', 'select-all', 'preview', 'load-more'])

const gridRef = ref(null)
const sentinelRef = ref(null)
const displayCount = ref(BATCH_SIZE)
let observer = null

// Provide scroll container to child ImageCards for IntersectionObserver
provide('scrollContainer', gridRef)

const visibleImages = computed(() =>
  props.isLocal ? props.images.slice(0, displayCount.value) : props.images
)
const hasMoreInternal = computed(() =>
  props.isLocal && displayCount.value < props.images.length
)
const hasMore = computed(() => hasMoreInternal.value || props.hasMoreExternal)
const selectedCount = computed(() => props.selectedIds.size)
const displayTotal = computed(() => props.totalCount ?? props.images.length)
const allSelected = computed(() =>
  props.images.length > 0 && props.selectedIds.size === props.images.length
)

const loadMore = () => {
  if (props.loading || props.loadingMore) return
  if (hasMoreInternal.value) {
    // Still have local images to reveal
    displayCount.value = Math.min(displayCount.value + BATCH_SIZE, props.images.length)
  } else if (props.hasMoreExternal) {
    // Need to fetch more from API
    emit('load-more')
  }
}

const onScroll = () => {
  // Fallback scroll handler if IntersectionObserver doesn't work
  if (!gridRef.value || !hasMore.value || props.loading || props.loadingMore) return
  const { scrollTop, scrollHeight, clientHeight } = gridRef.value
  if (scrollTop + clientHeight >= scrollHeight - 200) {
    loadMore()
  }
}

// Reset display count when local images are replaced
watch(() => props.images, (newImages, oldImages) => {
  if (props.isLocal) {
    const isAppend = oldImages && oldImages.length > 0 && newImages.length > oldImages.length && newImages[0] === oldImages[0]
    if (!isAppend) {
      displayCount.value = BATCH_SIZE
    }
  }
}, { deep: false })

const setupObserver = () => {
  if (observer) {
    observer.disconnect()
    observer = null
  }
  if (!gridRef.value) return

  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0]?.isIntersecting) {
        loadMore()
      }
    },
    {
      root: gridRef.value,
      rootMargin: '200px',
      threshold: 0
    }
  )

  if (sentinelRef.value) {
    observer.observe(sentinelRef.value)
  }
}

onMounted(() => {
  setupObserver()
})

// Re-initialize observer when scroll container or sentinel changes
watch([gridRef, sentinelRef], () => {
  setupObserver()
})

onUnmounted(() => {
  if (observer) {
    observer.disconnect()
    observer = null
  }
})
</script>

<style scoped>
.image-grid-container {
  display: flex;
  flex-direction: column;
  min-height: 0; /* Allow flex child to shrink below content size */
  overflow: hidden;
  background: #12121f;
}

.grid-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 1rem;
  background: #1a1a2e;
  border-bottom: 1px solid #2a2a4e;
}

.select-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.select-all {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.select-all input {
  width: 18px;
  height: 18px;
}

.deselect-btn {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  border: 1px solid #3a3a5e;
  background: transparent;
  color: #aaa;
  cursor: pointer;
  font-size: 0.8rem;
}

.deselect-btn:hover {
  background: #2a2a4e;
  color: white;
}

.grid-container {
  padding: 1rem;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.load-more-sentinel {
  grid-column: 1 / -1;
  min-height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-spinner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: #888;
  padding: 1rem;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 3px solid #333;
  border-top-color: #4a90d9;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading, .empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #888;
}
</style>
