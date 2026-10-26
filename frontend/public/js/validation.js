function textLength(value) {
    return typeof value === 'string' ? value.length : 0;
}

export function validateCallInput({ equipmentName, errorCode, symptom }) {
    const errors = {};
    if (typeof equipmentName !== 'string' || !equipmentName.trim() || textLength(equipmentName) > 100) {
        errors.equipmentName = '장비명은 1~100자로 입력해 주세요.';
    }
    if (typeof errorCode !== 'string' || !errorCode.trim() || textLength(errorCode) > 50) {
        errors.errorCode = '에러코드는 1~50자로 입력해 주세요.';
    }
    if (symptom !== undefined && symptom !== null && (typeof symptom !== 'string' || textLength(symptom) > 500)) {
        errors.symptom = '문제 내용은 500자 이하로 입력해 주세요.';
    }
    return errors;
}

export function normalizeSignupInput(input) {
    const normalized = { ...input };
    for (const field of ['clientName', 'companyName', 'position', 'username']) {
        if (typeof normalized[field] === 'string') normalized[field] = normalized[field].trim();
    }
    return normalized;
}

export function validateSignupInput({ clientName, companyName, position, username, password }) {
    const errors = {};
    if (typeof username !== 'string' || !/^[A-Za-z0-9_]{4,50}$/.test(username)) {
        errors.username = '아이디는 영문·숫자·밑줄 4~50자로 입력해 주세요.';
    }
    if (textLength(password) < 8 || textLength(password) > 64) {
        errors.password = '비밀번호는 8~64자로 입력해 주세요.';
    }
    const profile = { clientName, companyName, position };
    for (const [field, limit] of [['clientName', 20], ['companyName', 50], ['position', 30]]) {
        if (typeof profile[field] !== 'string' || !profile[field].trim() || profile[field].length > limit) {
            errors[field] = `${limit}자 이내로 입력해 주세요.`;
        }
    }
    return errors;
}

export function validateUtterance(text) {
    return typeof text === 'string' && text.trim().length > 0 && text.length <= 2000;
}
