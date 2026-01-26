"""自訂 CSS 樣式."""

CUSTOM_CSS = """
/* 頁首樣式 */
.header-box {
    background: linear-gradient(135deg, #b8860b 0%, #daa520 50%, #b8860b 100%);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
}

.header-box h1 {
    color: #1a1a2e !important;
    margin: 0 0 8px 0 !important;
}

.header-box p {
    color: #2c2c2c !important;
    margin: 4px 0 !important;
}

.header-box a {
    color: #1a1a2e !important;
    font-weight: 700;
    text-decoration: underline;
}

/* 伺服器標籤 */
.server-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 10px;
}

.server-tag {
    background: rgba(0,0,0,0.2);
    color: #1a1a2e;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 0.8em;
    font-weight: 600;
}

/* 狀態標籤 */
.status-badge {
    display: inline-block;
    background: #27ae60;
    color: #ffffff;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 0.85em;
    margin-top: 12px;
    font-weight: 500;
}

/* 分類 Radio 按鈕群組樣式 */
.category-radio {
    margin: 8px 0;
}

.category-radio .wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.category-radio label {
    padding: 6px 14px !important;
    border: 1px solid var(--border-color-primary) !important;
    border-radius: 8px !important;
    background: var(--background-fill-secondary) !important;
    cursor: pointer;
    transition: all 0.2s ease;
    font-size: 0.9em;
}

.category-radio label:hover {
    background: var(--background-fill-primary) !important;
    border-color: var(--color-accent) !important;
}

.category-radio input[type="radio"]:checked + span {
    background: var(--color-accent) !important;
    color: #1a1a2e !important;
    border-color: var(--color-accent) !important;
    font-weight: 600;
}

/* Gradio 5 相容 */
.category-radio .selected {
    background: var(--color-accent) !important;
    color: #1a1a2e !important;
    border-color: var(--color-accent) !important;
    font-weight: 600;
}
"""
