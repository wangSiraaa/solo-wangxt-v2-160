import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { WeightAudit } from '../models';

@Component({
  selector: 'app-weight-audit',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="panel">
      <h2>权重核对台
        <span class="right-note">人工设定与数据推得严格分开；常量列剔除后在剩余指标内归一</span>
      </h2>
      <table>
        <thead>
          <tr>
            <th class="rowhead">指标</th>
            <th>人工权重(原始)</th>
            <th>来源</th>
            <th>熵权(数据推得)</th>
            <th>有效份额</th>
            <th>口径</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let a of audit" [style.opacity]="a.excluded ? 0.55 : 1">
            <td class="rowhead">{{ a.criterion_code }}</td>
            <td>{{ a.manual_weight }}</td>
            <td style="text-align:left;white-space:normal;max-width:240px">{{ a.manual_source }}</td>
            <td>{{ a.entropy_weight === null ? '—' : (a.entropy_weight | number:'1.3-3') }}</td>
            <td>
              <div class="bar"><span [style.width]="(a.effective_share * 100) + '%'"></span></div>
              {{ (a.effective_share * 100) | number:'1.1-1' }}%
            </td>
            <td>{{ a.basis }}</td>
            <td style="text-align:left">
              <span class="chip excl" *ngIf="a.excluded">已剔除</span>
              <span class="chip benefit" *ngIf="!a.excluded">参与计算</span>
              <div class="muted" *ngIf="a.exclude_reason">{{ a.exclude_reason }}</div>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="muted" style="margin-top:8px">
        人工权重原始合计 = <b>{{ rawSum }}</b>（不要求等于 100；有效份额按参与计算的指标归一）。
        熵权完全来自数据离散度（信息熵越小 → 区分度越大 → 权重越大），不含任何人的偏好，
        因此"数据推得的第一"和"委员会想要的第一"可能不是同一件事。
      </p>
    </div>
  `,
})
export class WeightAuditComponent {
  @Input() audit: WeightAudit[] = [];
  @Input() rawSum = 0;
}
