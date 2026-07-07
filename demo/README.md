# ROAST. — promo video

A 20-second launch video for the World's 100 Best Coffee Shops explorer.

![ROAST.](https://yfc-ophey.github.io/Top-100-Best-CoffeeShops/) · **[Live site](https://yfc-ophey.github.io/Top-100-Best-CoffeeShops/)**

## What's here

| File | Description |
|------|-------------|
| `roast-brag.mp4` | The rendered video — 1920×1080, 20s, H.264 + AAC |
| `composition/` | Full reproducible [HyperFrames](https://hyperframes.heygen.com/) source (HTML + assets) |
| `CREDITS.md` | Music, font, and visual asset licenses |
| `share-copy.txt` | Ready-to-post social caption |
| `brag-plan.md`, `composition-brief.md` | Storyboard and composition brief |

## How it was built

Built from **real screenshots of the live site** (the world map, the ranked list, and the Onyx Coffee LAB detail card) with Ken Burns motion, the site's own dark-roast palette and fonts (Cabinet Grotesk / General Sans), and a café-jazz soundtrack.

Five beats: hook → map (`200 shops · 56 countries`) → two rankings → real shop detail card → outro lockup.

## Re-rendering

Requires [Node.js 22+](https://nodejs.org/) and [FFmpeg](https://ffmpeg.org/).

```bash
cd composition
npx hyperframes lint
npx hyperframes render --quality high --output ../roast-brag.mp4
```

Edit `composition/index.html` to change copy, timing, or assets, then re-render.

## Credits

See [`CREDITS.md`](./CREDITS.md). Music: "You Got Jazz" by Diego Nava (Mixkit free license). UI screenshots are of this project's own live site.
