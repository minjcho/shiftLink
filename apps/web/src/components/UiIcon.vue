<script setup lang="ts">
defineProps<{ name: 'inbox' | 'handover' | 'archive' | 'arrow' | 'plus' | 'note' }>();
const paths = {
  inbox: 'M4 4h16v16H4z M4 13h4l2 3h4l2-3h4',
  handover: 'M4 7h15m-4-4 4 4-4 4 M20 17H5m4-4-4 4 4 4',
  archive: 'M4 4h16v4H4z M6 8v12h12V8 M10 12h4',
  arrow: 'M5 12h14m-6-6 6 6-6 6',
  plus: 'M12 5v14 M5 12h14',
  note: 'M7 3h8l4 4v14H5V3h2 M14 3v5h5 M8 12h8 M8 16h5',
};
</script>
<template><svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[name]" /></svg></template>
