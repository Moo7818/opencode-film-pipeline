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

  var chart = echarts.init(document.getElementById('chart-cli'), null, { renderer: 'svg' });
  chart.setOption({
    animation: false,
    color: [accent2, accent],
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
    grid: { left: 8, right: 30, top: 44, bottom: 8, containLabel: true },
    xAxis: {
      type: 'value',
      name: 'CLI 往返次数',
      nameTextStyle: { color: muted, fontSize: 11 },
      axisLabel: { color: muted },
      splitLine: { lineStyle: { color: rule } }
    },
    yAxis: {
      type: 'category',
      data: ['阶段推进', '创建项目', '归档单产物', '素材归类（约10文件）', '资产同步（单集约12图）'],
      axisLabel: { color: ink, fontSize: 12 },
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false }
    },
    series: [
      {
        name: '现状（手工调用链）',
        type: 'bar',
        barWidth: 16,
        itemStyle: { color: accent2 },
        label: { show: true, position: 'right', color: muted, fontSize: 11 },
        data: [6, 11, 6, 13, 15]
      },
      {
        name: '脚本原子化后',
        type: 'bar',
        barWidth: 16,
        itemStyle: { color: accent },
        label: { show: true, position: 'right', color: muted, fontSize: 11 },
        data: [1, 2, 1, 1, 1]
      }
    ]
  });
  window.addEventListener('resize', function () { chart.resize(); });
})();
