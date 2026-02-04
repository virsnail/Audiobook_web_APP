/**
 * Markdown 与对齐数据的文本匹配工具
 * 
 * 核心算法：
 * 1. 将 Markdown 渲染为 HTML
 * 2. 遍历 alignment segments
 * 3. 使用模糊匹配（忽略标点、空格、数字格式差异）找到对应位置
 * 4. 用 <span data-segment-id="X" class="segment"> 包裹匹配文本
 */

import { marked } from 'marked';
import type { Segment } from '$lib/types/alignment';

/**
 * 标准化文本用于匹配
 * - 去除标点符号
 * - 统一数字格式（中文数字 → 阿拉伯数字）
 * - 去除多余空格
 */
function normalizeText(text: string): string {
  // 中文数字映射
  const chineseNumbers: Record<string, string> = {
    '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
    '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
    '零': '0'
  };
  
  let normalized = text
    // 转换中文数字
    .replace(/[一二三四五六七八九十零]/g, match => chineseNumbers[match] || match)
    // 去除常见标点
    .replace(/[，。、：；""''！？《》【】（）\-\—\.\,\:\;\"\'\!\?\(\)\[\]\/\\·*#_~`\n\r]/g, '')
    // 统一空白字符
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
  
  return normalized;
}

/**
 * 在 HTML 文本节点中查找并标记 segment
 */
function findAndMarkSegment(
  html: string, 
  segment: Segment, 
  searchStartIndex: number
): { html: string; foundIndex: number } {
  const normalizedSegment = normalizeText(segment.text);
  
  if (!normalizedSegment) {
    return { html, foundIndex: searchStartIndex };
  }
  
  // 从 HTML 中提取纯文本用于匹配
  // 我们需要维护一个映射：纯文本位置 → HTML 位置
  const textPositions: { textIndex: number; htmlIndex: number; char: string }[] = [];
  let textIndex = 0;
  let inTag = false;
  
  for (let i = 0; i < html.length; i++) {
    if (html[i] === '<') {
      inTag = true;
    } else if (html[i] === '>') {
      inTag = false;
    } else if (!inTag) {
      textPositions.push({ textIndex, htmlIndex: i, char: html[i] });
      textIndex++;
    }
  }
  
  // 从 searchStartIndex 开始搜索
  const plainText = textPositions.map(p => p.char).join('');
  const normalizedPlain = normalizeText(plainText);
  
  // 在标准化后的文本中查找
  let matchStart = -1;
  let matchLength = 0;
  
  // 使用滑动窗口匹配
  for (let i = 0; i < textPositions.length; i++) {
    // 构建从当前位置开始的标准化文本
    let windowText = '';
    let windowEnd = i;
    
    for (let j = i; j < textPositions.length && windowText.length < normalizedSegment.length * 3; j++) {
      windowText += textPositions[j].char;
      const normalizedWindow = normalizeText(windowText);
      
      if (normalizedWindow === normalizedSegment) {
        // 确保我们从 searchStartIndex 之后开始
        if (textPositions[i].htmlIndex >= searchStartIndex) {
          matchStart = i;
          matchLength = j - i + 1;
          break;
        }
      }
    }
    
    if (matchStart >= 0) break;
  }
  
  if (matchStart < 0) {
    // 未找到匹配，返回原始 HTML
    return { html, foundIndex: searchStartIndex };
  }
  
  // 计算 HTML 中的实际起始和结束位置
  const htmlStart = textPositions[matchStart].htmlIndex;
  const htmlEnd = textPositions[matchStart + matchLength - 1].htmlIndex + 1;
  
  // 检查是否已在其他标签内（如 <strong>）
  // 如果是，我们需要更聪明地处理
  const matchedHtml = html.slice(htmlStart, htmlEnd);
  
  // 插入 span 标记
  const markedHtml = 
    html.slice(0, htmlStart) +
    `<span data-segment-id="${segment.id}" class="segment">` +
    matchedHtml +
    '</span>' +
    html.slice(htmlEnd);
  
  return { 
    html: markedHtml, 
    foundIndex: htmlEnd + `<span data-segment-id="${segment.id}" class="segment"></span>`.length 
  };
}

/**
 * 将 segments 匹配到 Markdown 渲染后的 HTML
 */
export function matchSegmentsToMarkdown(
  markdownContent: string,
  segments: Segment[]
): string {
  // 配置 marked
  marked.setOptions({
    gfm: true,
    breaks: true,
  });
  
  // 渲染 Markdown 为 HTML
  let html = marked.parse(markdownContent) as string;
  
  // 按顺序匹配每个 segment
  let searchIndex = 0;
  
  for (const segment of segments) {
    const result = findAndMarkSegment(html, segment, searchIndex);
    html = result.html;
    searchIndex = result.foundIndex;
  }
  
  return html;
}

/**
 * 简化版：直接在 Markdown 渲染后的 HTML 中用正则匹配
 * 适用于对齐数据与 Markdown 文本高度一致的情况
 */
export function simpleMatchSegments(
  markdownContent: string,
  segments: Segment[]
): string {
  // 渲染 Markdown
  marked.setOptions({
    gfm: true,
    breaks: true,
  });
  
  let html = marked.parse(markdownContent) as string;
  
  // 对每个 segment，尝试直接匹配（使用更宽松的匹配）
  for (const segment of segments) {
    const text = segment.text.trim();
    if (!text) continue;
    
    // 转义正则特殊字符
    const escapedText = text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    
    // 创建宽松的正则表达式（允许中间有 HTML 标签）
    const pattern = escapedText
      .split('')
      .map(char => {
        // 对每个字符，允许其前后有 HTML 标签
        const escaped = char.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        return `(?:<[^>]*>)*${escaped}(?:<[^>]*>)*`;
      })
      .join('');
    
    try {
      const regex = new RegExp(`(${pattern})`, 'g');
      let matched = false;
      
      html = html.replace(regex, (match) => {
        if (!matched) {
          matched = true;
          return `<span data-segment-id="${segment.id}" class="segment">${match}</span>`;
        }
        return match;
      });
    } catch {
      // 正则匹配失败，跳过这个 segment
      console.warn(`Failed to match segment ${segment.id}: ${text.slice(0, 30)}...`);
    }
  }
  
  return html;
}

/**
 * 推荐使用的方法：基于文本位置的精确匹配
 */
export function matchByTextPosition(
  markdownContent: string,
  segments: Segment[]
): string {
  // 渲染 Markdown
  marked.setOptions({
    gfm: true,
    breaks: true,
  });
  
  let html = marked.parse(markdownContent) as string;
  
  // 创建一个 DOM 解析器来处理 HTML
  // 在 SSR 环境下使用简化版
  if (typeof DOMParser === 'undefined') {
    return simpleMatchSegments(markdownContent, segments);
  }
  
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');
  
  // 收集所有文本节点
  const textNodes: Text[] = [];
  const walker = document.createTreeWalker(
    doc.body,
    NodeFilter.SHOW_TEXT,
    null
  );
  
  let node: Text | null;
  while ((node = walker.nextNode() as Text | null)) {
    if (node.textContent?.trim()) {
      textNodes.push(node);
    }
  }
  
  // 对每个 segment 进行匹配
  for (const segment of segments) {
    const normalizedTarget = normalizeText(segment.text);
    if (!normalizedTarget) continue;
    
    // 在文本节点中查找
    for (const textNode of textNodes) {
      const nodeText = textNode.textContent || '';
      const normalizedNode = normalizeText(nodeText);
      
      // 检查这个节点是否包含我们要找的文本
      if (normalizedNode.includes(normalizedTarget)) {
        // 找到了！用 span 包裹
        const span = doc.createElement('span');
        span.setAttribute('data-segment-id', String(segment.id));
        span.className = 'segment';
        
        // 简单情况：整个节点就是我们要的
        if (normalizedNode === normalizedTarget) {
          textNode.parentNode?.insertBefore(span, textNode);
          span.appendChild(textNode);
        } else {
          // 复杂情况：需要拆分节点
          // 暂时用简单方法：包裹整个节点
          textNode.parentNode?.insertBefore(span, textNode);
          span.appendChild(textNode);
        }
        break;
      }
    }
  }
  
  return doc.body.innerHTML;
}

export default matchSegmentsToMarkdown;
