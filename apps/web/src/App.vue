<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { api, errorMessage, SessionChanged } from './lib/api';
import type { Build, Equipment, Me, Page } from './lib/types';
import ConnectedActionPanel from './features/actions/ConnectedActionPanel.vue';
import UiIcon from './components/UiIcon.vue';
import AppIcon from './components/AppIcon.vue';
import ResolutionPanel from './features/resolution/ResolutionPanel.vue';
import IncidentList from './features/intake/IncidentList.vue';
import IncidentDetail from './features/intake/IncidentDetail.vue';
import HandoverCreate from './features/handovers/HandoverCreate.vue';
import HandoverPage from './features/handovers/HandoverPage.vue';
const me = ref<Me | null>(null);
const build = ref<Build | null>(null);
const equipment = ref<Equipment[]>([]);
const account = ref('');
const sessionBusy = ref(false);
const sessionError = ref('');
const switchingNotice = ref('');
const epoch = ref(0);
const notice = ref('');
const incidentId = ref<string | null>(routeId());
const handoverId = ref<string | null>(handoverRouteId());
const workspace = ref(new URLSearchParams(location.search).get('view') ?? 'incidents');
const locationTitle = computed(() => handoverId.value ? '교대 인계 상세' : incidentId.value ? '사건 상세' : workspace.value === 'resolved' ? '해결 이력' : workspace.value === 'handovers' ? '교대 인계' : '사건 작업대');
function navigateWorkspace(value: string) { navigate(); workspace.value = value; history.replaceState({}, '', value === 'incidents' ? '/incidents' : `/incidents?view=${value}`); }
function chooseAccount(value: string) { account.value = value; void switchSession(); }
const accounts = [ ['reporter', '제보 작업자'], ['maintainer', '정비 담당자'], ['outgoing_supervisor', '출발 책임자'], ['incoming_supervisor', '수신 책임자'] ];
function routeId() { const value = location.pathname.match(/^\/incidents\/([^/]+)\/?$/); return value ? decodeURIComponent(value[1]) : null; }
function handoverRouteId() { const value = location.pathname.match(/^\/handovers\/([^/]+)\/?$/); return value ? decodeURIComponent(value[1]) : null; }
function pop() { workspace.value = new URLSearchParams(location.search).get('view') ?? 'incidents'; notice.value = ''; incidentId.value = routeId(); handoverId.value = handoverRouteId(); }
function navigate(id?: string, message = '') { workspace.value = 'incidents'; history.pushState({}, '', id ? `/incidents/${encodeURIComponent(id)}` : '/incidents'); incidentId.value = id ?? null; handoverId.value = null; notice.value = message; window.scrollTo({ top: 0 }); }
function navigateHandover(id: string) { history.pushState({}, '', `/handovers/${encodeURIComponent(id)}`); incidentId.value = null; handoverId.value = id; notice.value = ''; window.scrollTo({ top: 0 }); }
async function loadSession() {
  try {
    const session = await api.request<Me>('/me');
    const list = await api.request<Page<Equipment>>('/equipment');
    me.value = session.data; build.value = session.meta?.build ?? null; equipment.value = list.data.items;
    sessionError.value = '';
  } catch (error) { if (!(error instanceof SessionChanged)) sessionError.value = errorMessage(error); }
}
async function switchSession() {
  if (!account.value || sessionBusy.value) return;
  sessionBusy.value = true;
  api.invalidateSession(); epoch.value += 1;
  me.value = null; equipment.value = []; build.value = null; notice.value = ''; sessionError.value = '';
  switchingNotice.value = '계정이 전환되면 작성 중 입력과 대기 요청이 정리됩니다.';
  try { await api.request('/demo/session', 'POST', { account_key: account.value }); await loadSession(); }
  catch (error) { sessionError.value = errorMessage(error); }
  finally { sessionBusy.value = false; }
}
onMounted(() => { window.addEventListener('popstate', pop); void loadSession(); });
onUnmounted(() => window.removeEventListener('popstate', pop));
</script>
<template>
  <a href="#main" class="skip-link">본문으로 건너뛰기</a>
  <div class="app-shell">
    <aside class="sidebar" aria-label="주 탐색">
      <a class="brand" href="/incidents" @click.prevent="navigateWorkspace('incidents')"><span class="brand-symbol"><AppIcon name="link" /></span>ShiftLink<span class="brand-period">.</span></a>
      <nav class="primary-nav">
        <a href="/incidents" :aria-current="workspace === 'incidents' && !handoverId ? 'page' : undefined" @click.prevent="navigateWorkspace('incidents')"><UiIcon name="inbox" />사건 작업대<span class="nav-arrow">↗</span></a>
        <a href="/incidents?view=handovers" :aria-current="workspace === 'handovers' || handoverId ? 'page' : undefined" @click.prevent="navigateWorkspace('handovers')"><UiIcon name="handover" />교대 인계</a>
        <a href="/incidents?view=resolved" :aria-current="workspace === 'resolved' ? 'page' : undefined" @click.prevent="navigateWorkspace('resolved')"><UiIcon name="archive" />해결 이력</a>
      </nav>
      <span class="environment-label"><span></span>합성 데모 자료</span>
    </aside>
    <div class="main-shell">
      <header class="workspace-header">
        <div class="breadcrumb"><span>워크스페이스</span><span aria-hidden="true">/</span><strong>{{ locationTitle }}</strong></div>
        <div class="session-area"><details class="account-help"><summary>계정 전환 안내</summary><p>계정 전환 시 작성 중 입력과 대기 요청이 정리됩니다. 필요한 원문은 전환 전에 보관해 주세요.</p></details><div v-if="me" class="session-identity"><span class="avatar">{{ me.display_name.slice(0, 1) }}</span><div><strong>{{ me.display_name }}</strong><small>{{ me.role === 'supervisor' ? '책임자' : '작업자' }}</small></div></div>
          <form @submit.prevent="switchSession()"><label for="account" class="sr-only">데모 계정 전환</label><div class="inline-control"><select id="account" v-model="account" :disabled="sessionBusy" required><option disabled value="">계정 선택</option><option v-for="[key,name] in accounts" :key="key" :value="key">{{ name }}</option></select><button type="submit" class="secondary" :disabled="sessionBusy || !account">{{ sessionBusy ? '전환 중…' : '전환' }}</button></div></form>
        </div>
      </header>
      <main id="main" tabindex="-1">
        <p v-if="sessionError" class="notice error" role="alert">{{ sessionError }}</p>
        <p v-if="switchingNotice" class="session-help" role="status">{{ switchingNotice }}</p>
        <template v-if="me">
          <IncidentDetail v-if="incidentId" :key="`${epoch}-${incidentId}`" :id="incidentId" :me="me" :equipment="equipment" :notice="notice" @back="navigate()" @open-handover="navigateHandover">
            <template #actions="{ detail, session, refresh }"><ConnectedActionPanel :detail="detail" :session="session" :refresh="refresh" /></template>
            <template #resolution="{ detail, session, refresh }"><ResolutionPanel :detail="detail" :session="session" :refresh="refresh" /></template>
          </IncidentDetail>
          <HandoverPage v-else-if="handoverId" :key="`${epoch}-handover-${handoverId}`" :id="handoverId" :me="me" @back="navigateWorkspace('handovers')" @open-incident="navigate" />
          <section v-else-if="workspace === 'handovers'" class="handover-workspace view-enter"><header class="page-heading"><div><p class="eyebrow">HANDOVER / 교대 책임 이전</p><h1>교대 인계</h1><p class="muted">남은 업무를 확인하고, 다음 책임자에게 연결하세요.</p></div><UiIcon name="handover" class="heading-icon" /></header><HandoverCreate :key="`handover-create-${epoch}`" :me="me" @created="navigateHandover" /><div class="handover-guide"><span class="section-number">인계 내용 다시 열기</span><h2>사건에서 인계 기록을 확인하세요.</h2><p>사건 상세의 교대 인수 요약 또는 전달받은 인계 링크에서 항목별 내용을 읽고 인수할 수 있습니다.</p><button class="secondary" @click="navigateWorkspace('incidents')">사건 작업대 열기 <span aria-hidden="true">↗</span></button></div></section>
          <IncidentList v-else :key="`${epoch}-${workspace}`" :equipment="equipment" :initial-status="workspace === 'resolved' ? 'RESOLVED' : ''" :archive="workspace === 'resolved'" @open="navigate"><template #handover><HandoverCreate v-if="workspace !== 'resolved'" :key="`handover-create-${epoch}`" :me="me" @created="navigateHandover" /></template></IncidentList>
        </template>
        <section v-else class="welcome view-enter"><div class="welcome-mark"><AppIcon name="link" /></div><p class="eyebrow">다음 교대까지, 빈틈없이</p><h1>현장의 기록을<br>해결까지 연결해요</h1><p>담당 역할에 따라 제보, 작업 수행, 인수와 최종 확인을 진행합니다.</p><div class="account-options"><button v-for="[key,name] in accounts" :key="key" :disabled="sessionBusy" @click="chooseAccount(key)"><span>{{ name }}</span><UiIcon name="arrow" /></button></div><p v-if="sessionBusy" role="status">세션 전환 중…</p><button v-if="sessionError" class="secondary" @click="loadSession()">세션 다시 확인</button><small>합성 데모 자료로 진행하는 업무 흐름입니다.</small></section>
      </main>
      <footer class="app-footer"><span>ShiftLink <span aria-hidden="true">·</span> 사람의 확인으로 완성되는 업무</span><details v-if="build"><summary>실행 정보</summary><p>앱 {{ build.app_commit_sha ?? 'UNKNOWN' }} · 미커밋 변경 {{ build.working_tree_dirty === null ? 'UNKNOWN' : build.working_tree_dirty ? '있음' : '없음' }} · Agent {{ build.agent_mode ?? 'UNKNOWN' }} · 검색 {{ build.search_mode ?? 'UNKNOWN' }}</p><p>소프트웨어 시험용 합성 자료입니다. 설비 조작·재가동·안전을 승인하지 않습니다.</p></details></footer>
    </div>
  </div>
</template>
