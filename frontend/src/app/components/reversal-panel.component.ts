import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReversalReport } from '../models';

@Component({
  selector: 'app-reversal-panel',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="panel" *ngIf="report">
      <h2>排名逆转实验：删除「{{ report.dropped_label }}」</h2>
      <div class="two-col">
        <table>
          <thead><tr><th colspan="3">完整候选集</th></tr>
          <tr><th>名次</th><th class="rowhead">候选</th><th>WSM 分</th></tr></thead>
          <tbody>
            <tr *ngFor="let r of report.full_ranking">
              <td>{{ r.rank }}</td><td class="rowhead">{{ r.candidate_code }}</td>
              <td>{{ r.score | number:'1.3-3' }}</td>
            </tr>
          </tbody>
        </table>
        <table>
          <thead><tr><th colspan="3">删除后</th></tr>
          <tr><th>名次</th><th class="rowhead">候选</th><th>WSM 分</th></tr></thead>
          <tbody>
            <tr *ngFor="let r of report.reduced_ranking">
              <td>{{ r.rank }}</td><td class="rowhead">{{ r.candidate_code }}</td>
              <td>{{ r.score | number:'1.3-3' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h3>逐候选变化</h3>
      <table>
        <thead>
          <tr><th class="rowhead">候选</th><th>原名次</th><th>新名次</th><th>位移</th><th>主要驱动列</th><th style="text-align:left">解释</th></tr>
        </thead>
        <tbody>
          <tr *ngFor="let r of report.rows">
            <td class="rowhead">{{ r.candidate_name }} ({{ r.candidate_code }})</td>
            <td>{{ r.rank_full }}</td><td>{{ r.rank_reduced }}</td>
            <td [class.shift-pos]="r.shift > 0" [class.shift-neg]="r.shift < 0">
              {{ r.shift === 0 ? '—' : (r.shift > 0 ? '↑ ' : '↓ ') + abs(r.shift) }}
            </td>
            <td>{{ r.driver_criterion }}</td>
            <td style="text-align:left;white-space:normal;max-width:420px">{{ r.explanation }}</td>
          </tr>
        </tbody>
      </table>

      <h3>每列贡献变化（均值绝对差）</h3>
      <div class="pill-row">
        <span class="chip" *ngFor="let d of report.drivers">{{ d.criterion }}: Δ={{ d.mean_abs_contribution_change }}</span>
      </div>

      <div class="warnbox blue">{{ report.note }}</div>
      <div class="warnbox" *ngFor="let e of report.explanations">{{ e }}</div>
    </div>
  `,
})
export class ReversalPanelComponent {
  @Input() report: ReversalReport | null = null;
  abs = Math.abs;
}
