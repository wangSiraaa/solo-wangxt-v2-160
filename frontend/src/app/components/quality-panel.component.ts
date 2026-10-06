import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DuplicateInfo, OutlierCell } from '../models';

@Component({
  selector: 'app-quality-panel',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="panel">
      <h2>数据质量与口径告警</h2>

      <div class="warnbox red" *ngFor="let d of duplicates">
        疑似重复指标：<b>{{ d.criterion_a }}</b> 与 <b>{{ d.criterion_b }}</b>
        （Pearson={{ d.pearson }}, Spearman={{ d.spearman }}）。
        {{ d.effect }}。可在左侧把其中一个指标移出计算，再看排名如何变化。
      </div>

      <div class="warnbox" *ngFor="let o of outliers">
        极端异常值：<b>{{ o.candidate }} / {{ o.criterion }} = {{ o.value }}</b>，
        修正 z 分数 = {{ o.modified_z }}（MAD 口径）。默认只标记不改写；
        开启"MAD 裁剪"后它会被截断，且步骤 2 矩阵会变化。
      </div>

      <div class="warnbox blue" *ngFor="let w of otherWarnings">{{ w }}</div>

      <p class="muted" *ngIf="!duplicates.length && !outliers.length && !otherWarnings.length">
        当前情景无告警。
      </p>
    </div>
  `,
})
export class QualityPanelComponent {
  @Input() duplicates: DuplicateInfo[] = [];
  @Input() outliers: OutlierCell[] = [];
  @Input() warnings: string[] = [];

  get otherWarnings(): string[] {
    return this.warnings.filter(
      (w) => !w.startsWith('极端异常值') && !w.startsWith('缺失值'),
    );
  }
}
