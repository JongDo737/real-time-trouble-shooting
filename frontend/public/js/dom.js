// HTML 문자열을 결합합니다. 외부 값은 escapeHTML로 처리합니다.

export function html(parts, ...values) {
    return parts.reduce((result, part, index) => result + part + (index < values.length ? String(values[index]) : ''), '');
}

export function openDialog(container, dialog) {
    const opener = document.activeElement;
    container.append(dialog);
    dialog.showModal();
    trapFocus(dialog);
    dialog.addEventListener('close', () => {
        dialog.remove();
        opener?.focus();
    }, { once: true });
}

// Tab 키가 열린 모달 안에서만 이동하게 합니다.
function trapFocus(dialog) {
    dialog.addEventListener('keydown', event => {
        if (event.key !== 'Tab') return;
        const elements = [
            ...dialog.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]')
        ];
        const first = elements[0];
        const last = elements.at(-1);
        if (!first) {
            event.preventDefault();
            return;
        }
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        }
        else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    });
}
