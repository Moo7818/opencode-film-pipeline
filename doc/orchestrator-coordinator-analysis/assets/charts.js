(function () {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  if (window.mermaid) {
    mermaid.initialize({ startOnLoad: true, theme: 'neutral', securityLevel: 'loose' });
  }

  // --- Chart: coordinator 技能文档体积构成 ---
  var docChart = echarts.init(document.getElementById('chart-docsize'), null, { renderer: 'svg' });
  docChart.setOption({
    animation: false,
    color: [accent, accent2, accent + '99', accent2 + '99', muted, muted + '99'],
    tooltip: {
      trigger: 'item',
      appendToBody: true,
      formatter: '{b}: {c} KB ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: 4,
      top: 'middle',
      itemWidth: 12,
      itemHeight: 12,
      textStyle: { color: muted, fontSize: 12 }
    },
    series: [{
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['36%', '50%'],
      label: { show: false },
      itemStyle: { borderColor: bg2, borderWidth: 2 },
      data: [
        { name: 'SKILL.md（主文档）', value: 37 },
        { name: 'project_management.md', value: 21 },
        { name: 'stages.md（阶段定义）', value: 8.5 },
        { name: 'manifest.md（归档规范）', value: 5.5 },
        { name: 'events.md（事件规范）', value: 3.7 },
        { name: 'logs.md（日志聚合）', value: 1.5 }
      ]
    }]
  });
  window.addEventListener('resize', function () { docChart.resize(); });

  // --- Chart: spawn 次数估算对比 ---
  var spawnChart = echarts.init(document.getElementById('chart-spawn'), null, { renderer: 'svg' });
  spawnChart.setOption({
    animation: false,
    color: [accent, accent2],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      appendToBody: true
    },
    legend: {
      top: 0,
      itemWidth: 12,
      itemHeight: 12,
      textStyle: { color: muted, fontSize: 12 }
    },
    grid: { left: 8, right: 24, top: 44, bottom: 8, containLabel: true },
    xAxis: {
      type: 'value',
      name: 'spawn 次数',
      nameTextStyle: { color: muted, fontSize: 11 },
      axisLabel: { color: muted },
      splitLine: { lineStyle: { color: rule } }
    },
    yAxis: {
      type: 'category',
      data: ['现状：逐阶段交接', '建议：里程碑批量推进', '建议：执行者直报+批量复核'],
      axisLabel: { color: ink, fontSize: 12 },
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false }
    },
    series: [
      {
        name: '执行类 spawn',
        type: 'bar',
        stack: 'total',
        barWidth: 30,
        itemStyle: { color: accent },
        data: [15, 15, 15]
      },
      {
        name: 'coordinator 类 spawn',
        type: 'bar',
        stack: 'total',
        barWidth: 30,
        itemStyle: { color: accent2 },
        label: {
          show: true,
          position: 'right',
          color: muted,
          fontSize: 11,
          formatter: function (p) {
            var totals = [27, 20, 18];
            return '合计约 ' + totals[p.dataIndex] + ' 次';
          }
        },
        data: [12, 5, 3]
      }
    ]
  });
  window.addEventListener('resize', function () { spawnChart.resize(); });
})();
