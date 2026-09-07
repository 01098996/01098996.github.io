# Weixin wire-format reference

The standalone `scripts/weixin_bridge.py` client follows the API schema and QR login sequence documented by Tencent's MIT-licensed [openclaw-weixin](https://github.com/Tencent/openclaw-weixin), inspected at version 2.4.8 on 2026-09-07. The applicable copyright and license are included in `scripts/TENCENT-LICENSE.txt`.

The client does not install, import or run OpenClaw. It implements text-only daily-digest delivery. The service may require renewed login or a fresh conversation context; recurring unsolicited delivery is not assumed to be guaranteed.
