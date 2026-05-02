<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useFilesStore } from '@/stores/prometheus/files'
import FileTree from '@/components/prometheus/files/FileTree.vue'
import FileBreadcrumb from '@/components/prometheus/files/FileBreadcrumb.vue'
import FileToolbar from '@/components/prometheus/files/FileToolbar.vue'
import FileList from '@/components/prometheus/files/FileList.vue'
import FileContextMenu from '@/components/prometheus/files/FileContextMenu.vue'
import FileEditor from '@/components/prometheus/files/FileEditor.vue'
import FilePreview from '@/components/prometheus/files/FilePreview.vue'
import FileUploadModal from '@/components/prometheus/files/FileUploadModal.vue'
import FileRenameModal from '@/components/prometheus/files/FileRenameModal.vue'
import type { FileEntry } from '@/api/prometheus/files'

const filesStore = useFilesStore()

const contextMenuRef = ref<InstanceType<typeof FileContextMenu> | null>(null)
const showUpload = ref(false)
const showRenameModal = ref(false)
const renameMode = ref<'newFile' | 'newFolder' | 'rename'>('newFile')
const renameEntry = ref<FileEntry | null>(null)

function handleContextMenu(e: MouseEvent, entry: FileEntry) {
  contextMenuRef.value?.show(e, entry)
}

function handleShowNewFile() {
  renameMode.value = 'newFile'
  renameEntry.value = null
  showRenameModal.value = true
}

function handleShowNewFolder() {
  renameMode.value = 'newFolder'
  renameEntry.value = null
  showRenameModal.value = true
}

function handleRename(entry: FileEntry) {
  renameMode.value = 'rename'
  renameEntry.value = entry
  showRenameModal.value = true
}

onMounted(() => {
  filesStore.fetchEntries('')
})
</script>

<template>
  <div class="files-view">
    <div class="files-tree-panel">
      <FileTree />
    </div>
    <div class="files-main-panel">
      <FileToolbar
        @show-new-file="handleShowNewFile"
        @show-new-folder="handleShowNewFolder"
        @show-upload="showUpload = true"
      />
      <FileBreadcrumb />
      <div class="files-content">
        <FileEditor v-if="filesStore.editingFile" />
        <FilePreview v-else-if="filesStore.previewFile" />
        <FileList v-else @contextmenu-entry="handleContextMenu" />
      </div>
    </div>
    <FileContextMenu ref="contextMenuRef" @rename="handleRename" />
    <FileUploadModal v-model:show="showUpload" />
    <FileRenameModal v-model:show="showRenameModal" :mode="renameMode" :entry="renameEntry" />
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as *;

.files-view {
  display: flex;
  height: 100%;
  overflow: hidden;
}

.files-tree-panel {
  width: 240px;
  min-width: 180px;
  max-width: 400px;
  border-right: 1px solid $border-color;
  overflow-y: auto;
  flex-shrink: 0;
}

.files-main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.files-content {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

@media (max-width: $breakpoint-mobile) {
  .files-view {
    flex-direction: column;
  }

  .files-tree-panel {
    width: 100%;
    max-width: none;
    height: 200px;
    border-right: none;
    border-bottom: 1px solid $border-color;
  }
}
</style>
