import { HttpClient } from '@angular/common/http';
import { Injectable, signal } from '@angular/core';
import {
  Candidate, Criterion, Report, ReversalReport, Version,
} from './models';

const API = '';

@Injectable({ providedIn: 'root' })
export class McdaService {
  health = signal<string>('连接中…');

  constructor(private http: HttpClient) {
    this.http.get<{ backend: string }>(`${API}/health`).subscribe({
      next: (h) => this.health.set(h.backend),
      error: () => this.health.set('后端不可用'),
    });
  }

  getCriteria() {
    return this.http.get<Criterion[]>(`${API}/criteria`);
  }

  getCandidates() {
    return this.http.get<Candidate[]>(`${API}/candidates`);
  }

  getVersions() {
    return this.http.get<Version[]>(`${API}/versions`);
  }

  analyze(body: Record<string, unknown>) {
    return this.http.post<Report>(`${API}/analyze`, body);
  }

  versionReport(id: number) {
    return this.http.get<Report>(`${API}/versions/${id}/report`);
  }

  reversal(body: Record<string, unknown>) {
    return this.http.post<ReversalReport>(`${API}/reversal`, body);
  }

  setValue(candidate_id: number, criterion_id: number, value: number | null) {
    return this.http.post(`${API}/values`, { candidate_id, criterion_id, value });
  }
}
