<script setup lang="ts">
import {
  NConfigProvider,
  NDialogProvider,
  NMessageProvider,
  NNotificationProvider,
} from 'naive-ui'
</script>

<template>
  <NConfigProvider>
    <NDialogProvider>
      <NMessageProvider>
        <NNotificationProvider>
          <slot />
        </NNotificationProvider>
      </NMessageProvider>
    </NDialogProvider>
  </NConfigProvider>
</template>
