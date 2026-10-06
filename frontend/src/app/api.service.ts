import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import {
  Analysis,
  DecisionDetail,
  MissingPolicy,
  Scenario,
  VersionSnapshot,
  WeightOrigin,
} from './models';

const BASE = '/api';

export interface AnalyzeRequest {
  weight_set_id?: number | null;
  weights_override?: Record<string, number> | null;
  use_derived: WeightOrigin;
  missing_policy: MissingPolicy;
}

export interface FreezeRequest extends AnalyzeRequest {
  label: string;
  method: 'wsm' | 'topsis';
  comment: string;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  scenarios(): Observable<Scenario[]> {
    return this.http.get<Scenario[]>(`${BASE}/scenarios`);
  }

  decision(id: number): Observable<DecisionDetail> {
    return this.http.get<DecisionDetail>(`${BASE}/decisions/${id}`);
  }

  derivedWeights(
    id: number,
    missingPolicy: MissingPolicy
  ): Observable<unknown> {
    return this.http.get(
      `${BASE}/decisions/${id}/derived-weights?missing_policy=${missingPolicy}`
    );
  }

  analyze(id: number, body: AnalyzeRequest): Observable<Analysis> {
    return this.http.post<Analysis>(
      `${BASE}/decisions/${id}/analyze`, body
    );
  }

  freeze(id: number, body: FreezeRequest): Observable<{ id: number }> {
    return this.http.post<{ id: number }>(
      `${BASE}/decisions/${id}/versions`, body
    );
  }

  version(id: number): Observable<VersionSnapshot> {
    return this.http.get<VersionSnapshot>(`${BASE}/versions/${id}`);
  }

  saveWeightSet(
    id: number,
    body: {
      name: string;
      method: 'manual' | 'entropy' | 'critic';
      source: string;
      weights: Record<string, number>;
    }
  ): Observable<unknown> {
    return this.http.post(
      `${BASE}/decisions/${id}/weight-sets`, body
    );
  }
}
