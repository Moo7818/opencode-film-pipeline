(function () {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();

  if (window.mermaid) {
    mermaid.initialize({ startOnLoad: true, theme: 'neutral', securityLevel: 'loose' });
  }

  var chart = echarts.init(document.getElementById('chart-latency'), null, { renderer: 'svg' });
  chart.setOption({
    animation: false,
    color: [accent2, accent],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      appendToBody: true,
      valueFormatter: function (v) { return v + ' 秒'; }
    },
    legend: {
      top: 0,
      itemWidth: 12,
      itemHeight: 12,
      textStyle: { color: muted, fontSize: 12 }
    },
    grid: { left: 8, right: 40, top: 44, bottom: 8, containLabel: true },
    xAxis: {
      type: 'value',
      name: '耗时（秒，对数轴）',
      nameTextStyle: { color: muted, fontSize: 11 },
      axisLabel: { color: muted },
      splitLine: { lineStyle: { color: rule } },
      logBase: 10,
      min: 0.05
    },
    yAxis: {
      type: 'category',
      data: ['创建项目（含配置确认）', '跨项目状态查询', '单个阶段推进', '批量注册 10 个资产'],
      axisLabel: { color: ink, fontSize: 12 },
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false }
    },
    series: [
      {
        name: '现状（JSON + LLM 逐步执行）',
        type: 'bar',
        barWidth: 16,
        itemStyle: { color: accent2 },
        label: {
          show: true,
          position: 'right',
          color: muted,
          fontSize: 11,
          formatter: function (p) { return p.value + ' 秒'; }
        },
        data: [120, 10, 45, 90]
      },
      {
        name: '脚本原子化 + SQLite',
        type: 'bar',
        barWidth: 16,
        itemStyle: { color: accent },
        label: {
          show: true,
          position: 'right',
          color: muted,
          fontSize: 11,
          formatter: function (p) { return p.value + ' 秒'; }
        },
        data: [5, 0.1, 1, 2]
      }
    ]
  });
  window.addEventListener('resize', function () { chart.resize(); });
})();
