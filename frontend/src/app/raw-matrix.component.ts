import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { Alternative, Criterion } from './models';
import { KIND_SHORT, fmt } from './format';

@Component({
  selector: 'app-raw-matrix',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="panel">
      <h2>① 原始指标矩阵（PostgreSQL 中保存的原始值与单位）</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>候选方案</th>
              <th *ngFor="let c of criteria">
                {{ c.label }}
                <div class="sub">
                  <span class="kind" [class]="c.kind">{{ KIND_SHORT[c.kind] }}</span>
                  {{ c.unit || '无单位' }}
                  <span *ngIf="c.kind === 'target'">
                    目标 [{{ c.target_low }}, {{ c.target_high }}]
                  </span>
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let a of alternatives; let i = index">
              <td class="alt">{{ a.label }}</td>
              <td *ngFor="let c of criteria; let j = index"
                  [class.missing]="raw[i][j] === null">
                <ng-container *ngIf="raw[i][j] !== null; else miss">
                  {{ fmt(raw[i][j]) }}
                </ng-container>
                <ng-template #miss>
                  <span class="missing-badge">缺失</span>
                </ng-template>
                <div class="note" *ngIf="notes[i]?.[j]">{{ notes[i][j] }}</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="hint">
        方向不是装饰：{{ '成本型' }}按“越小越好”反向规范化，目标区间型按“区间内满分、
        区间外按距离衰减”规范化。缺失一律标红，绝不替换成 0 或满分。
      </p>
    </section>
  `,
})
export class RawMatrixComponent {
  @Input() criteria: Criterion[] = [];
  @Input() alternatives: Alternative[] = [];
  @Input() raw: (number | null)[][] = [];
  @Input() notes: string[][] = [];
  KIND_SHORT = KIND_SHORT;
  fmt = fmt;
}
