import { configureCodingSettings } from '../capabilities/coding-settings/store'
import { createCodingSettingsController } from '../capabilities/coding-settings/controller'
import { createCodingSettingsGateway } from '../capabilities/coding-settings/gateway'
import { configureCodingWorkspace } from '../modules/coding/stores/coding.store'
import { createCodingController } from '../modules/coding/presentation/coding-controller'
import { createCodingGateway } from '../modules/coding/infrastructure/coding-gateway'
import { observeCoding } from '../modules/coding/presentation/coding-observer'
import { configureChatWorkspace } from '../modules/chat/stores/chat.store'
import { configureImageWorkspace } from '../modules/image-studio/stores/image-studio.store'
import { configureAudioWorkspace } from '../modules/audio-studio/stores/audio-studio.store'
import { createAudioController } from '../modules/audio-studio/presentation/audio-controller'
import { createAudioGateway } from '../modules/audio-studio/infrastructure/audio-gateway'
import { configureModelsWorkspace } from '../modules/models/stores/models.store'
import { configureRuntimeOverview } from '../capabilities/runtime/store'
import { createRuntimeController } from '../capabilities/runtime/controller'
import { createRuntimeGateway } from '../capabilities/runtime/gateway'
import { toRef } from 'vue'
import { createEndpoints } from '@mlx-studio/api-client'
import { runtimeClient } from '../platform/runtime-bridge'
import { useModelDirectory } from '../capabilities/models'
import { JobObserver } from '../capabilities/jobs/job-observer'
import { createChatGateway } from '../modules/chat/infrastructure/chat-gateway'
import { createChatController } from '../modules/chat/presentation/chat-controller'
import { createImageGateway } from '../modules/image-studio/infrastructure/image-gateway'
import { createImageController } from '../modules/image-studio/presentation/image-controller'
import { createModelsGateway } from '../modules/models/infrastructure/models-gateway'
import { createModelsController } from '../modules/models/presentation/models-controller'
import { exportBlob, pickModelDirectory, pickProjectDirectory } from '../platform/files'
import { createAttachmentGateway } from '../modules/chat/infrastructure/attachment-gateway'
import { createChatDraftController } from '../modules/chat/presentation/chat-draft-controller'
import { configureWebSearch } from '../capabilities/web-search/store'
import { createWebSearchController } from '../capabilities/web-search/controller'
import { createWebSearchGateway } from '../capabilities/web-search/gateway'

const observer = new JobObserver(runtimeClient)
function directoryDependencies() {
  const directory = useModelDirectory()
  return {
    directory,
    refreshModels: () =>
      directory.refresh(async () => createEndpoints(await runtimeClient()).models.list()),
  }
}
export function createChatWorkspace() {
  const { directory, refreshModels } = directoryDependencies()
  const gateway = createChatGateway(runtimeClient)
  return createChatController({
    gateway,
    draftFactory: (conversation) =>
      createChatDraftController(
        conversation,
        createAttachmentGateway(runtimeClient),
        (id, enabled) => gateway.update(id, { web_search_enabled: enabled }),
      ),
    models: toRef(directory, 'items'),
    refreshModels,
    exportText: (content, filename) =>
      exportBlob(new Blob([content], { type: 'text/markdown;charset=utf-8' }), filename),
    observe: (id, after, event, resync) => observer.watch(id, after, { event, resync }),
  })
}
export function createImageWorkspace() {
  return createImageController({
    ...directoryDependencies(),
    gateway: createImageGateway(runtimeClient),
    exportImage: (blob, id) => exportBlob(blob, `mlx-studio-${id}.png`),
  })
}
export function createModelsWorkspace() {
  return createModelsController({
    directory: useModelDirectory(),
    gateway: createModelsGateway(runtimeClient),
    pickDirectory: pickModelDirectory,
  })
}

export function createAudioWorkspace() {
  return createAudioController({
    ...directoryDependencies(),
    gateway: createAudioGateway(runtimeClient),
    exportAudio: (blob, id) => exportBlob(blob, `mlx-studio-${id}.wav`),
  })
}

export function createRuntimeOverview() {
  return createRuntimeController({
    gateway: createRuntimeGateway(runtimeClient),
    exportFile: exportBlob,
  })
}

export function createCodingWorkspace() {
  const { directory, refreshModels } = directoryDependencies()
  return createCodingController({
    gateway: createCodingGateway(runtimeClient),
    models: toRef(directory, 'items'),
    refreshModels,
    pickDirectory: pickProjectDirectory,
    observe: (after, refresh, fail, apply) =>
      observeCoding(runtimeClient, after, refresh, fail, apply),
  })
}

export function installWorkspaces(): void {
  configureWebSearch(() => createWebSearchController(createWebSearchGateway(runtimeClient)))
  configureCodingSettings(() =>
    createCodingSettingsController(createCodingSettingsGateway(runtimeClient)),
  )
  configureCodingWorkspace(createCodingWorkspace)
  configureChatWorkspace(createChatWorkspace)
  configureImageWorkspace(createImageWorkspace)
  configureAudioWorkspace(createAudioWorkspace)
  configureModelsWorkspace(createModelsWorkspace)
  configureRuntimeOverview(createRuntimeOverview)
}
