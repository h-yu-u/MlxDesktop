<script setup lang="ts">
import {
  NConfigProvider,
  darkTheme,
  type GlobalThemeOverrides,
  NDialogProvider,
  NMessageProvider,
  NNotificationProvider,
} from 'naive-ui'
const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#7785ff', primaryColorHover: '#939dff', primaryColorPressed: '#5967ed',
    bodyColor: '#111722', cardColor: '#1b2333', modalColor: '#1b2333', popoverColor: '#222c3f',
    textColorBase: '#edf0fa', textColor1: '#f0f2fc', textColor2: '#c2cbde', textColor3: '#8e9ab1',
    borderColor: '#303c52', borderRadius: '10px', fontFamily: 'inherit',
  },
  Button: { heightMedium: '40px', fontWeight: '500' },
  Slider: { fillColor: '#6586ff', fillColorHover: '#869aff', railColor: '#354057', handleSize: '17px' },
  Input: { color: '#161e2d', colorFocus: '#192132', borderHover: '1px solid #6579cf' },
  Select: { peers: { InternalSelection: { color: '#20293b', colorActive: '#20293b' } } },
}
</script>

<template>
  <NConfigProvider
    :theme="darkTheme"
    :theme-overrides="themeOverrides"
  >
    <NDialogProvider>
      <NMessageProvider>
        <NNotificationProvider>
          <slot />
        </NNotificationProvider>
      </NMessageProvider>
    </NDialogProvider>
  </NConfigProvider>
</template>
