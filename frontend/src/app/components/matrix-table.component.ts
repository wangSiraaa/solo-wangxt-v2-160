import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { StepTrace } from '../models';

@Component({
  selector: 'app-matrix-table',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="panel">
      <h2>{{ step.name }}</h2>
      <p class="muted">{{ step.description }}</p>
      <div class="scrollx">
        <table>
          <thead>
            <tr>
              <th class="rowhead">候选 ＠ 指标</th>
              <th *ngFor="let c of step.columns">{{ c }}</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let row of step.matrix; let i = index">
              <td class="rowhead">{{ step.rows[i] }}</td>
              <td *ngFor="let v of row; let j = index"
                  [class.null]="v === null || v === undefined"
                  [class.missing-cell]="isMarked(i, j)"
                  [style.--h]="heatAlpha(v)">
                <ng-container *ngIf="v !== null && v !== undefined; else na">
                  {{ v | number:'1.3-3' }}
                </ng-container>
                <ng-template #na>—</ng-template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <ul class="step-notes" *ngIf="step.notes?.length">
        <li *ngFor="let n of step.notes">{{ n }}</li>
      </ul>
    </div>
  `,
})
export class MatrixTableComponent {
  @Input() step!: StepTrace;
  @Input() heat = true;
  /** 需要描边标注的单元格（如插补/裁剪），"行,列" 集合 */
  @Input() marks = new Set<string>();

  isMarked(i: number, j: number): boolean {
    return this.marks.has(`${i},${j}`);
  }

  heatAlpha(v: number | null | undefined): string {
    if (v === null || v === undefined || !this.heat) return '0';
    const a = Math.max(0, Math.min(1, Number(v)));
    return (0.06 + 0.55 * a).toFixed(3);
  }
}
