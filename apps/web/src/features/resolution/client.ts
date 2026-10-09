import { api, ApiClient } from '../../lib/api';
import type { Envelope } from '../../lib/types';
import type { VerificationResult } from './types';

/** Validate before Command clears its receipt key; a malformed 200 is uncertain. */
class VerificationClient extends ApiClient {
  override get sessionEpoch() { return api.sessionEpoch; }
  override async request<T>(path: string, method = 'GET', body?: unknown, key?: string): Promise<Envelope<T>> {
    const response = await api.request<T>(path, method, body, key);
    const result = response.data as VerificationResult | undefined;
    const decision = (body as { decision?: string } | undefined)?.decision;
    if (!result || !result.incident_id || !result.verification_id || !Number.isInteger(result.incident_version) || result.incident_version < 1 ||
        (decision === 'RESOLVE' ? result.incident_status !== 'RESOLVED' || !result.case_id || !result.resolved_at
          : result.incident_status !== 'INVESTIGATING' || result.case_id !== null || result.resolved_at !== null)) {
      throw new Error('검증 저장 응답을 확인하지 못했습니다.');
    }
    return response;
  }
}
export const verificationClient = new VerificationClient();
