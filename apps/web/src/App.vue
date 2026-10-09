<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';
import { api, errorMessage, SessionChanged } from './lib/api';
import type { Build, Equipment, Me, Page } from './lib/types';
import IncidentList from './features/intake/IncidentList.vue';
import IncidentDetail from './features/intake/IncidentDetail.vue';
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
const accounts = [ ['reporter', '제보 작업자'], ['maintainer', '정비 담당자'], ['outgoing_supervisor', '출발 책임자'], ['incoming_supervisor', '수신 책임자'] ];
function routeId() { const value = location.pathname.match(/^\/incidents\/([^/]+)\/?$/); return value ? decodeURIComponent(value[1]) : null; }
function pop() { notice.value = ''; incidentId.value = routeId(); }
function navigate(id?: string, message = '') { history.pushState({}, '', id ? `/incidents/${encodeURIComponent(id)}` : '/incidents'); incidentId.value = id ?? null; notice.value = message; window.scrollTo({ top: 0 }); }
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
  switchingNotice.value = '계정을 전환하며 작성 중 입력과 이전 계정의 재전송 대기를 정리했습니다.';
  try { await api.request('/demo/session', 'POST', { account_key: account.value }); await loadSession(); }
  catch (error) { sessionError.value = errorMessage(error); }
  finally { sessionBusy.value = false; }
}
onMounted(() => { window.addEventListener('popstate', pop); void loadSession(); });
onUnmounted(() => window.removeEventListener('popstate', pop));
</script>
<template>
  <a href="#main" class="skip-link">본문으로 건너뛰기</a>
  <header class="app-header"><div class="header-inner"><a class="brand" href="/incidents" @click.prevent="navigate()"><span class="brand-mark">S</span>ShiftLink<span class="brand-subtitle">현장 기록의 연결</span></a><span class="demo-pill">합성 데모 자료</span><div class="session-area"><div v-if="me" class="session-identity"><strong>{{ me.display_name }}</strong><small>{{ me.role }} · {{ me.duties.join(', ') }}</small></div><form @submit.prevent="switchSession()"><label for="account">데모 계정 전환</label><div class="inline-control"><select id="account" v-model="account" :disabled="sessionBusy" required><option disabled value="">계정 선택</option><option v-for="[key,name] in accounts" :key="key" :value="key">{{ name }}</option></select><button type="submit" class="secondary" :disabled="sessionBusy || !account">{{ sessionBusy ? '전환 중…' : '전환' }}</button></div></form></div></div></header>
  <main id="main" tabindex="-1"><p v-if="switchingNotice" class="notice" role="status">{{ switchingNotice }}</p><p class="session-help">계정 전환 시 작성 중 입력과 대기 요청이 정리됩니다. 필요한 원문은 전환 전에 보관해 주세요.</p><p v-if="sessionError" class="notice error" role="alert">{{ sessionError }}</p><template v-if="me"><p class="site-label">사업장 {{ me.site_id }} · 교대 {{ me.shift_occurrence_id ?? '미배정' }}</p><IncidentDetail v-if="incidentId" :key="`${epoch}-${incidentId}`" :id="incidentId" :me="me" :equipment="equipment" :notice="notice" @back="navigate()" /><IncidentList v-else :key="epoch" :equipment="equipment" @open="navigate" /></template><section v-else class="welcome panel"><p class="eyebrow">ShiftLink 합성 데모</p><h1>기록할 사람으로<br>시작하세요.</h1><p>상단에서 데모 계정을 선택하면 서버가 해당 역할의 세션을 시작합니다.</p><p v-if="sessionBusy" role="status">세션 전환 중…</p><button v-if="sessionError" class="secondary" @click="loadSession()">세션 다시 확인</button></section></main>
  <footer><span>ShiftLink · 접수 / AI 조사 / 담당자 확인</span><details v-if="build"><summary>실행 환경</summary><p>앱 {{ build.app_commit_sha ?? 'UNKNOWN' }} · 미커밋 변경 {{ build.working_tree_dirty === null ? 'UNKNOWN' : build.working_tree_dirty ? '있음' : '없음' }} · Agent {{ build.agent_mode ?? 'UNKNOWN' }} · 검색 {{ build.search_mode ?? 'UNKNOWN' }}</p></details><p>소프트웨어 시험용 합성 자료입니다. 설비 조작·재가동·안전을 승인하지 않습니다.</p></footer>
</template>
