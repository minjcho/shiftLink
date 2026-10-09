<script setup lang="ts">
import AppIcon from './AppIcon.vue'
defineEmits<{ start: [] }>()
</script>
<template>
  <section class="workflow-banner" aria-labelledby="workflow-banner-title">
    <div class="banner-copy">
      <span class="banner-label">기록은 남기고, 업무는 이어가고</span>
      <h2 id="workflow-banner-title">교대가 바뀌어도<br>놓치는 일이 없도록</h2>
      <p>현장의 제보와 남은 작업을 한곳에서 연결해요.</p>
      <button class="banner-link" @click="$emit('start')">현장 기록 남기기<AppIcon name="arrow" /></button>
    </div>
    <div class="handoff-art" aria-hidden="true">
      <div class="art-orbit"></div>
      <div class="art-sheet back"><span class="art-line"></span><span class="art-line short"></span><span class="art-checkbox"><AppIcon name="check" /></span></div>
      <div class="art-sheet front"><span class="art-sheet-icon"><AppIcon name="document" /></span><span class="art-line"></span><span class="art-line short"></span><span class="art-line"></span></div>
      <span class="art-transfer"><AppIcon name="swap" /></span><span class="art-spark spark-one"></span><span class="art-spark spark-two"></span>
    </div>
  </section>
</template>
