<script setup lang="ts">
defineProps<{id?:string}>()
</script>
<template><section class="panel"><h1>교대 인수</h1><p v-if="id" class="muted">인계 {{ id }}</p><slot name="handover"><p>교대 인계와 인수 확인 기능을 준비 중입니다.</p></slot></section></template>
