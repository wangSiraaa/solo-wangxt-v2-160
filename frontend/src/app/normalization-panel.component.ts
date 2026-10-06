import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import {
  Alternative,
  Criterion,
  MissingCell,
  NormalizationMeta,
} from './models';
import { fmt } from './format';

@Component({
  selector: 'app-normalization-panel',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="panel">
      <h2>② 第一步转换：按方向规范化到 0–1</h2>

      <div class="formulas">
        <div class="card" *ngFor="let m of meta"
             [class.const]="m.constant" [class.anchor]="m.anchored">
          <h3>{{ m.label }}</h3>
          <code>{{ m.formula }}</code>
          <p class="hint">
            观测范围 [{{ fmt(m.observed_min) }}, {{ fmt(m.observed_max) }}]
            {{ m.unit ? '（' + m.unit + '）' : '' }}；
            锚点 [{{ fmt(m.anchor_min) }}, {{ fmt(m.anchor_max) }}]
            <span *ngIf="m.constant"> · 常量列 → 中性 0.5，不给满分</span>
            <span *ngIf="m.missing_count"> · {{ m.missing_count }} 个缺失</span>
          </p>
        </div>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>候选方案</th>
              <th *ngFor="let c of criteria">{{ c.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let a of alternatives; let i = index">
              <td class="alt">{{ a.label }}</td>
              <td *ngFor="let c of criteria; let j = index"
                  [class.imputed]="isImputed(a.key, c.key)"
                  [class.missing]="matrix[i][j] === null">
                {{ fmt(matrix[i][j]) }}
                <span *ngIf="isImputed(a.key, c.key)" class="imp">补</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <ul class="warnings" *ngIf="warnings.length">
        <li *ngFor="let w of warnings">⚠️ {{ w }}</li>
      </ul>

      <details *ngIf="missingCells.length" open>
        <summary>缺失值逐格处理记录（{{ missingCells.length }}）</summary>
        <ul>
          <li *ngFor="let cell of missingCells">
            {{ cell.alternative }} × {{ cell.criterion }}：
            策略「{{ policyLabel(cell.policy) }}」→
            {{ cell.imputed === null ? '该格不参与，行内权重重归一' : fmt(cell.imputed) }}
          </li>
        </ul>
      </details>
    </section>
  `,
})
export class NormalizationPanelComponent {
  @Input() criteria: Criterion[] = [];
  @Input() alternatives: Alternative[] = [];
  @Input() matrix: (number | null)[][] = [];
  @Input() meta: NormalizationMeta[] = [];
  @Input() warnings: string[] = [];
  @Input() missingCells: MissingCell[] = [];

  fmt = fmt;

  isImputed(alt: string, crit: string): boolean {
    return this.missingCells.some(
      (c) => c.alternative === alt && c.criterion === crit
    );
  }

  policyLabel(p: string): string {
    return { neutral: '中性 0.5', row_mean: '该行已知项均值',
             exclude_weight: '剔除该指标并重归一权重' }[p] ?? p;
  }
}
