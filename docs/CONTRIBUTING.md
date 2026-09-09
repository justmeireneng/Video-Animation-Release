# Contributing to Video Animation Studio

C?m ?n b?n ?? quan t?m ??ng g?p cho d? ?n **Video Animation**!

---

## Quy Tr?nh ??ng G?p (Contribution Workflow)

1. **Fork** kho l?u tr? v? t?i kho?n c? nh?n c?a b?n.
2. T?o nh?nh t?nh n?ng m?i t? nh?nh `main`:
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. Tu?n th? c?c nguy?n t?c thi?t k?:
   - **Semantic First**: M?i t?nh n?ng visual ph?i ph?c v? l?i d?n truy?n.
   - **Provider Abstraction**: Khi th?m m? h?nh AI m?i, lu?n k? th?a t? c?c l?p abstract trong `src/providers/base.py`.
   - **No Secrets in Repo**: Tuy?t ??i kh?ng hardcode API keys trong m? ngu?n.
4. Vi?t unit test b? sung trong th? m?c `tests/`.
5. ??m b?o to?n b? test v??t qua:
   ```bash
   python -m unittest discover -s tests
   ```
6. Commit thay ??i v?i th?ng ?i?p r? r?ng theo chu?n [Conventional Commits](https://www.conventionalcommits.org/):
   ```bash
   git commit -m "feat(provider): add Veo 2 vertex provider adapter"
   ```
7. ??y m? ngu?n l?n fork v? t?o **Pull Request** v?o nh?nh `main`.
