import { configureChatWorkspace } from '../modules/chat/stores/chat.store'
import { configureImageWorkspace } from '../modules/image-studio/stores/image-studio.store'
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
import { exportBlob, pickModelDirectory } from '../platform/files'

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
  return createChatController({
    gateway: createChatGateway(runtimeClient),
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

export function createRuntimeOverview() {
  return createRuntimeController({
    gateway: createRuntimeGateway(runtimeClient),
    exportFile: exportBlob,
  })
}

export function installWorkspaces(): void {
  configureChatWorkspace(createChatWorkspace)
  configureImageWorkspace(createImageWorkspace)
  configureModelsWorkspace(createModelsWorkspace)
  configureRuntimeOverview(createRuntimeOverview)
}
