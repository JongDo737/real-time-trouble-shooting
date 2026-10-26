package com.realshoot.backend.auth;

import java.time.Instant;

import com.realshoot.backend.global.Times;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

/** users — ADMIN = 한국 응대직원, USER = 글로벌 고객사 */
@Entity
@Table(name = "users")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 50)
    private String username;

    @Column(name = "client_name", nullable = false, length = 20)
    private String clientName;

    @Column(name = "company_name", nullable = false, length = 50)
    private String companyName;

    @Column(nullable = false, length = 30)
    private String position;

    @Column(name = "password_hash", nullable = false)
    private String passwordHash;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Role role;

    @Column(name = "created_at")
    private Instant createdAt;

    /** 회원가입은 항상 USER. ADMIN은 scripts/create-admin.sh로만 만든다 */
    public static User signup(String username, String passwordHash, String clientName, String companyName,
                              String position) {
        User user = new User();
        user.username = username;
        user.passwordHash = passwordHash;
        user.clientName = clientName;
        user.companyName = companyName;
        user.position = position;
        user.role = Role.USER;
        return user;
    }

    /** 기동 시 테스트 ADMIN 계정용. 회원가입 API는 signup()만 사용한다. */
    public static User create(String username, String passwordHash, String clientName, String companyName,
                              String position, Role role) {
        User user = new User();
        user.username = username;
        user.passwordHash = passwordHash;
        user.clientName = clientName;
        user.companyName = companyName;
        user.position = position;
        user.role = role;
        return user;
    }

    /** 이미 있는 admin 테스트 계정을 ADMIN · 지정 비밀번호로 맞춘다. */
    public void applyTestAdmin(String passwordHash) {
        this.passwordHash = passwordHash;
        this.role = Role.ADMIN;
    }

    @PrePersist
    void prePersist() {
        if (createdAt == null) {
            createdAt = Times.now();
        }
    }
}
