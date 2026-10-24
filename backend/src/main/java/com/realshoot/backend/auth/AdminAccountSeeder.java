package com.realshoot.backend.auth;

import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/** 로컬 테스트용 ADMIN 한 개. 같은 username이 USER로 있어도 ADMIN과 비밀번호를 맞춘다. */
@Slf4j
@Component
@RequiredArgsConstructor
public class AdminAccountSeeder implements ApplicationRunner {

    private static final String USERNAME = "admin";
    private static final String PASSWORD = "test1234";

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    @Override
    @Transactional
    public void run(ApplicationArguments args) {
        var existing = userRepository.findByUsername(USERNAME);
        if (existing.isEmpty()) {
            userRepository.save(User.create(USERNAME, passwordEncoder.encode(PASSWORD), "관리자", "본사", "상담원",
                    Role.ADMIN));
            log.info("테스트 ADMIN 계정을 만들었습니다. username={}", USERNAME);
            return;
        }
        User user = existing.get();
        if (user.getRole() == Role.ADMIN && passwordEncoder.matches(PASSWORD, user.getPasswordHash())) {
            return;
        }
        user.applyTestAdmin(passwordEncoder.encode(PASSWORD));
        log.info("기존 {} 계정을 ADMIN으로 맞췄습니다.", USERNAME);
    }
}
