import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RankRow } from '../models';

@Component({
  selector: 'app-rank-table',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="panel">
      <h2>{{ title }}</h2>
      <table>
        <thead>
          <tr>
            <th>名次</th><th class="rowhead">候选</th>
            <th>{{ scoreLabel }}</th><th>条形</th>
            <ng-container *ngIf="showTopsis">
              <th>D+ 距正理想</th><th>D- 距负理想</th><th>贴近度 C</th>
            </ng-container>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let r of rows">
            <td [class.rank1]="r.rank === 1">{{ r.rank }}</td>
            <td class="rowhead">{{ r.candidate_name }} <span class="muted">({{ r.candidate_code }})</span></td>
            <td>{{ score(r) | number:'1.3-3' }}</td>
            <td style="min-width:140px">
              <div class="bar"><span [class.red]="title.includes('WSM') === false"
                [style.width]="(score(r) * 100) + '%'"></span></div>
            </td>
            <ng-container *ngIf="showTopsis">
              <td>{{ r.distance_ideal | number:'1.3-3' }}</td>
              <td>{{ r.distance_anti_ideal | number:'1.3-3' }}</td>
              <td [class.rank1]="r.rank === 1">{{ r.closeness_ideal | number:'1.3-3' }}</td>
            </ng-container>
          </tr>
        </tbody>
      </table>
      <p class="muted" *ngIf="note" style="margin-top:8px">{{ note }}</p>
    </div>
  `,
})
export class RankTableComponent {
  @Input() title = '';
  @Input() scoreLabel = '得分';
  @Input() rows: RankRow[] = [];
  @Input() showTopsis = false;
  @Input() note = '';

  score(r: RankRow): number {
    return this.showTopsis ? (r.closeness_ideal ?? 0) : (r.wsm_score ?? 0);
  }
}
