package com.realshoot.backend.auth;

/** 역할은 두 개뿐이고, 언어는 역할로 고정 (USER = en, ADMIN = ko) */
public enum Role {
    USER("en"),
    ADMIN("ko");

    private final String lang;

    Role(String lang) {
        this.lang = lang;
    }

    public String lang() {
        return lang;
    }

    /** 대화 상대 역할 (번역 대상 언어 결정용) */
    public Role counterpart() {
        return this == USER ? ADMIN : USER;
    }
}
