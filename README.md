# wuwa-match3-bot

鳴潮「無音消除」三消活動的自動遊玩腳本。遊戲 client 區域須為 1280x720。

先進入關卡，再執行：

```bash
python bot.py --dry
```

只讀盤並顯示下一步，不操作。

```bash
python bot.py
```

自動遊玩。`--moves N` 限制步數。

遊戲須保持在前景，因為 Unreal 讀取真實游標，背景視窗訊息無效。按 F8、切走視窗、或棋盤連續 12 秒無法辨識（如結算畫面）時會停止，並把最後一幀存到 `captures/last_stop.png`。

| 檔案 | 用途 |
| --- | --- |
| `win.py` | 尋找遊戲視窗 |
| `capture.py` | PrintWindow 截圖 |
| `vision.py` | 辨識 8x7 棋盤與特殊棋 |
| `solver.py` | 模擬交換與連鎖，選分數最高的一步 |
| `inputs.py` | SendInput 滑鼠拖動 |
| `test_vision.py` | 用存檔畫面離線檢查辨識 |

未驗證：爆炸棋辨識（尚未在畫面中出現）、棋盤尺寸不同的關卡、帶特殊障礙棋的關卡。無法辨識的格子視為不可移動。
