<script setup lang="ts">
defineProps<{ name: 'link' | 'grid' | 'swap' | 'arrow' | 'check' | 'equipment' | 'clock' | 'document' | 'shield' | 'refresh' | 'plus' | 'person' }>()
const paths = {
  link: 'M10 13a5 5 0 0 0 7 .2l3-3a5 5 0 0 0-7-7l-2 2 M14 11a5 5 0 0 0-7-.2l-3 3a5 5 0 0 0 7 7l2-2',
  grid: 'M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z',
  swap: 'M4 8h16m-4-4 4 4-4 4 M20 16H4m4-4-4 4 4 4',
  arrow: 'm9 5 7 7-7 7', check: 'm5 12 4 4L19 6',
  equipment: 'M4 8h16v12H4z M8 8V4h8v4 M8 12v4 M12 12v4 M16 12v4',
  clock: 'M12 8v5l3 2 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  document: 'M14 3H5v18h14V8z M14 3v5h5 M9 12h6 M9 16h4',
  shield: 'M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7z m-4 9 3 3 5-5',
  refresh: 'M20 7v5h-5 M4 17v-5h5 M6 6a8 8 0 0 1 13 3 M18 18A8 8 0 0 1 5 15',
  plus: 'M12 5v14 M5 12h14',
  person: 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-2a8 8 0 0 1 16 0v2',
}
</script>
<template><svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[name]" /></svg></template>
