const fs = require('fs');
const { chromium } = require('playwright');

async function checkDOM() {
  const browser = await chromium.launch({ headless: false, channel: 'chrome' });
  const page = await browser.newPage();

  await page.goto('https://www.znzmo.com/?from=personalCenter');
  await page.waitForTimeout(5000);

  const initialUrl = page.url();
  const initialTitle = page.title();
  console.log(`当前 URL: ${initialUrl}`);
  console.log(`当前标题: ${initialTitle}`);

  // 获取页面 DOM
  const pageHTML = await page.content();
  fs.writeFileSync('znzmo_full.html', pageHTML, 'utf8');
  console.log('完整页面 HTML 已保存到 znzmo_full.html');

  // 查找用户相关的元素
  const userElements = await page.evaluate(() => {
    // 查找所有可能是用户头像或登录按钮的元素
    const allDivs = document.querySelectorAll('*');
    const candidates = [];

    for (let el of allDivs) {
      try {
        // 查找包含用户、头像、登录相关类名或属性的元素
        const classes = el.className || '';
        const id = el.id || '';
        const innerText = el.innerText || '';
        const html = el.innerHTML || '';

        // 检查常见的用户相关模式
        if (
          el.tagName === 'A' && el.getAttribute('href') && (
            el.getAttribute('href').includes('login') ||
            el.getAttribute('href').includes('personalCenter')
          ) ||
          el.tagName === 'IMG' && (
            classes.includes('avatar') ||
            classes.includes('user') ||
            id.includes('avatar') ||
            id.includes('user')
          ) ||
          classes.includes('user') ||
          classes.includes('avatar') ||
          classes.includes('login') ||
          id.includes('user') ||
          id.includes('login') ||
          id.includes('avatar') ||
          innerText.includes('登') ||
          innerText.includes('录') ||
          innerText.includes('Login') ||
          innerText.includes('Sign')
        ) {
          candidates.push({
            tag: el.tagName,
            id,
            class: classes,
            text: innerText.trim(),
            href: el.tagName === 'A' ? el.getAttribute('href') : null,
            src: el.tagName === 'IMG' ? el.getAttribute('src') : null
          });
        }
      } catch {
        // 忽略异常
      }
    }

    return candidates.slice(0, 50); // 只返回前50个
  });

  console.log('\n找到的用户相关元素:');
  userElements.forEach((el, index) => {
    console.log(`\n${index + 1}`);
    if (el.text) console.log(`  文本: ${el.text}`);
    if (el.id) console.log(`  ID: ${el.id}`);
    if (el.class) console.log(`  类名: ${el.class}`);
    if (el.href) console.log(`  链接: ${el.href}`);
    if (el.src) console.log(`  图片: ${el.src}`);
  });

  // 截图
  await page.screenshot({ path: 'znzmo_check_dom_screenshot.png', fullPage: true });

  // 查找 script 标签
  const scripts = await page.evaluate(() => {
    const allScripts = [];
    const scriptTags = document.querySelectorAll('script');
    for (let s of scriptTags) {
      allScripts.push(s.innerText.slice(0, 200));
    }
    return allScripts;
  });

  console.log('\n找到的 <script> 标签:');
  scripts.slice(0, 10).forEach((s, index) => {
    console.log(`\n${index + 1}`);
    console.log(s);
  });

  console.log('\n');
  await browser.close();
}

checkDOM();
