const CARD_SYMBOLS = [
  '🌟','🌙','☀️','⭐','🔮','🌊','🔥','🌿','⚡','🦋',
  '🌸','🦅','🐍','🦁','🌹','💎','🗡️','⚖️','🏔️','🌈',
  '🎭','🌀'
];

const ZODIAC_SYMBOLS = {
  '白羊座':'♈','金牛座':'♉','双子座':'♊','巨蟹座':'♋',
  '狮子座':'♌','处女座':'♍','天秤座':'♎','天蝎座':'♏',
  '射手座':'♐','摩羯座':'♑','水瓶座':'♒','双鱼座':'♓'
};

let currentMethod = 'tarot';

// 方法切换
document.querySelectorAll('.method-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.method-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentMethod = btn.dataset.method;

    document.getElementById('tarot-options').style.display =
      currentMethod === 'tarot' ? 'block' : 'none';
    document.getElementById('zodiac-options').style.display =
      currentMethod === 'zodiac' ? 'block' : 'none';

    document.getElementById('result').style.display = 'none';
  });
});

// 占卜按钮
document.getElementById('divine-btn').addEventListener('click', async () => {
  const question = document.getElementById('question').value.trim();
  const btn = document.getElementById('divine-btn');
  const btnText = btn.querySelector('.btn-text');
  const btnLoading = btn.querySelector('.btn-loading');

  btn.disabled = true;
  btnText.style.display = 'none';
  btnLoading.innerHTML = '<span class="loading-spinner"></span>占卜中…';
  btnLoading.style.display = 'inline';

  document.getElementById('result').style.display = 'none';

  try {
    let data;
    if (currentMethod === 'tarot') {
      data = await callAPI('/api/tarot', {
        question,
        spread: document.getElementById('spread-select').value
      });
      renderTarot(data);
    } else if (currentMethod === 'iching') {
      data = await callAPI('/api/iching', { question });
      renderIching(data);
    } else if (currentMethod === 'zodiac') {
      const sign = document.getElementById('sign-select').value;
      const birthday = document.getElementById('birthday').value;
      if (!sign) { alert('请选择星座'); return; }
      data = await callAPI('/api/zodiac', { question, sign, birthday });
      renderZodiac(data, sign);
    } else if (currentMethod === 'fortune') {
      data = await callAPI('/api/fortune', { question });
      renderFortune(data);
    }

    document.getElementById('result').style.display = 'block';
    document.getElementById('result').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    alert('占卜失败，请检查 API Key 是否配置正确');
    console.error(e);
  } finally {
    btn.disabled = false;
    btnText.style.display = 'inline';
    btnLoading.style.display = 'none';
  }
});

async function callAPI(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function renderTarot(data) {
  const cardsEl = document.getElementById('result-cards');
  cardsEl.innerHTML = '';

  data.drawn.forEach((d, i) => {
    const symbol = CARD_SYMBOLS[d.card.id % CARD_SYMBOLS.length];
    const card = document.createElement('div');
    card.className = 'tarot-card';
    card.style.animationDelay = `${i * 0.15}s`;
    card.innerHTML = `
      <div class="position">${d.position}</div>
      <div class="card-symbol">${symbol}</div>
      <div class="card-name">${d.card.name}</div>
      ${d.reversed ? '<div class="card-reversed">逆位</div>' : ''}
      <div class="card-meaning">${d.meaning}</div>
    `;
    cardsEl.appendChild(card);
  });

  document.getElementById('result-interpretation').textContent = data.interpretation;
}

function renderIching(data) {
  const cardsEl = document.getElementById('result-cards');
  const h = data.hexagram;

  let linesHtml = data.primary_lines.map((line, i) => {
    const isChanging = data.changing[i];
    const cls = `hex-line ${line === 1 ? 'yang' : 'yin'}${isChanging ? ' changing' : ''}`;
    if (line === 1) {
      return `<div class="${cls}"><div class="hex-line-bar"></div>${isChanging ? ' ○' : ''}</div>`;
    } else {
      return `<div class="${cls}">
        <div class="hex-line-bar"></div>
        <div style="width:12px"></div>
        <div class="hex-line-bar"></div>
        ${isChanging ? ' ×' : ''}
      </div>`;
    }
  }).join('');

  let changeHtml = '';
  if (data.changed_hexagram) {
    changeHtml = `<div style="margin-top:12px;color:var(--text-dim);font-size:0.85rem">
      变卦：<span style="color:var(--accent)">${data.changed_hexagram.title}</span>
    </div>`;
  }

  cardsEl.innerHTML = `
    <div class="hexagram-display">
      <div class="hexagram-name">${h.title}</div>
      <div class="hexagram-lines">${linesHtml}</div>
      <div style="color:var(--text-dim);font-size:0.85rem">${h.keywords.join(' · ')}</div>
      ${changeHtml}
    </div>
  `;

  document.getElementById('result-interpretation').textContent = data.interpretation;
}

function renderZodiac(data, sign) {
  const cardsEl = document.getElementById('result-cards');
  const symbol = ZODIAC_SYMBOLS[sign] || '⭐';

  cardsEl.innerHTML = `
    <div class="zodiac-card">
      <div class="zodiac-symbol">${symbol}</div>
      <div class="zodiac-name">${sign}</div>
    </div>
  `;

  document.getElementById('result-interpretation').textContent = data.interpretation;
}

function renderFortune(data) {
  const cardsEl = document.getElementById('result-cards');
  const f = data.fortune;
  const gradeClass = f.grade.replace(/签$/, '签');

  cardsEl.innerHTML = `
    <div class="fortune-display">
      <div class="fortune-number">${f.number}</div>
      <div class="fortune-grade ${f.grade}">${f.grade}</div>
      <div class="fortune-poem">${f.poem}</div>
    </div>
  `;

  document.getElementById('result-interpretation').textContent = data.interpretation;
}
