import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { VersionSnapshot } from './models';
import { fmt, rankBadge } from './format';

@Component({
  selector: 'app-version-viewer',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="overlay" *ngIf="snapshot" (click)="close.emit()">
      <div class="modal" (click)="$event.stopPropagation()">
        <button class="x" (click)="close.emit()">×</button>
        <h2>决策版 #{{ snapshot.id }}：{{ snapshot.label }}</h2>
        <p class="hint">
          {{ snapshot.created_at | date:'yyyy-MM-dd HH:mm' }} ·
          {{ snapshot.created_by }} · 模型 {{ snapshot.method | uppercase }}
        </p>
        <div class="card">
          <h3>委员会备注</h3>
          <p>{{ s.comment || '（无）' }}</p>
        </div>
        <div class="card">
          <h3>冻结时的权重与来源</h3>
          <p>
            来源：<span class="tag">{{ s.weight_provenance.origin }}</span>
            {{ s.weight_provenance.source }}
          </p>
          <table class="wtab inline">
            <tr *ngFor="let c of s.criteria; let j = index">
              <td>{{ c.label }}</td><td>{{ fmt(s.weight_vector[j]) }}</td>
            </tr>
          </table>
        </div>
        <div class="card">
          <h3>冻结时的排名</h3>
          <table>
            <tr *ngFor="let a of s.alternatives; let i = index">
              <td class="rank">{{ rankBadge(s.ranking[i]) }}</td>
              <td class="alt">{{ a.label }}</td>
              <td>{{ fmt(s.scores[i]) }}</td>
            </tr>
          </table>
        </div>
        <div class="card warn" *ngIf="s.audits.duplicates.length || s.audits.outliers.length">
          <h3>当时未解决的数据问题（一并存档）</h3>
          <ul>
            <li *ngFor="let d of s.audits.duplicates">
              重复指标：{{ d.a_label }} / {{ d.b_label }}（ρ={{ d.spearman }}）
            </li>
            <li *ngFor="let o of s.audits.outliers">
              异常值：{{ o.alternative }} 的 {{ o.criterion_label }} = {{ o.value }}
            </li>
          </ul>
        </div>
      </div>
    </div>
  `,
})
export class VersionViewerComponent {
  @Input() snapshot: VersionSnapshot | null = null;
  @Output() close = new EventEmitter<void>();

  fmt = fmt;
  rankBadge = rankBadge;

  get s() {
    return this.snapshot!.snapshot;
  }
}
