import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import {
  DuplicateFinding,
  OutlierFinding,
} from './models';

@Component({
  selector: 'app-audit-panel',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="panel audit">
      <h2>数据体检（在任何打分之前）</h2>

      <div class="grid">
        <div class="card" [class.warn]="duplicates.length">
          <h3>重复指标 × {{ duplicates.length }}</h3>
          <p class="hint">
            两个指标排名完全一致时，同时计入等于把该维度的权重翻倍——总分会
            “悄悄”偏向它，但权重表上看不出来。系统只报告、不自动合并，去留由委员会决定。
          </p>
          <ul>
            <li *ngFor="let d of duplicates">
              <strong>{{ d.a_label }}</strong> 与
              <strong>{{ d.b_label }}</strong>
              <span class="tag" [class.ok]="d.same_direction">
                Spearman ρ = {{ d.spearman }}
                （{{ d.same_direction ? '同向' : '反向' }}）
              </span>
              <p class="hint">{{ d.issue }}</p>
            </li>
          </ul>
          <p *ngIf="!duplicates.length" class="ok-text">未发现完全同排名的指标对。</p>
        </div>

        <div class="card" [class.warn]="outliers.length">
          <h3>极端异常值 × {{ outliers.length }}</h3>
          <p class="hint">
            基于中位数 + MAD 的稳健 z 分数（|z| ≥ 3.5）与 IQR 三倍围栏。
            极端值在 min/max 规范化中独占 0/1 端点，会把其余方案压扁。
          </p>
          <ul>
            <li *ngFor="let o of outliers">
              <strong>{{ o.alternative }}</strong> 的
              「{{ o.criterion_label }}」= {{ o.value }} {{ o.unit }}
              <span class="tag">稳健 z = {{ o.robust_z }}</span>
              <span class="hint">（中位数 {{ o.median }} {{ o.unit }}）</span>
              <p class="hint">{{ o.issue }}</p>
            </li>
          </ul>
          <p *ngIf="!outliers.length" class="ok-text">未发现极端异常值。</p>
        </div>
      </div>
    </section>
  `,
})
export class AuditPanelComponent {
  @Input() duplicates: DuplicateFinding[] = [];
  @Input() outliers: OutlierFinding[] = [];
}
