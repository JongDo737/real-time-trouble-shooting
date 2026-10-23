package com.realshoot.backend.auth;

import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.realshoot.backend.auth.AuthDtos.LoginRequest;
import com.realshoot.backend.auth.AuthDtos.LoginResponse;
import com.realshoot.backend.auth.AuthDtos.SignupRequest;
import com.realshoot.backend.auth.AuthDtos.UserInfo;
import com.realshoot.backend.global.error.ApiException;
import com.realshoot.backend.global.error.ErrorCode;
import com.realshoot.backend.security.JwtProvider;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtProvider jwtProvider;

    @Transactional
    public void signup(SignupRequest request) {
        if (userRepository.existsByUsername(request.username())) {
            throw new ApiException(ErrorCode.DUPLICATE_USERNAME);
        }
        User user = User.signup(request.username(), passwordEncoder.encode(request.password()),
                request.clientName(), request.companyName(), request.position());
        try {
            userRepository.saveAndFlush(user);
        } catch (DataIntegrityViolationException e) {
            // 동시에 같은 아이디로 가입한 경우 (username UNIQUE)
            throw new ApiException(ErrorCode.DUPLICATE_USERNAME);
        }
    }

    /** 아이디 없음 · 비밀번호 불일치를 구분하지 않음 */
    @Transactional(readOnly = true)
    public LoginResponse login(LoginRequest request) {
        User user = userRepository.findByUsername(request.username())
                .filter(u -> passwordEncoder.matches(request.password(), u.getPasswordHash()))
                .orElseThrow(() -> new ApiException(ErrorCode.INVALID_CREDENTIALS));
        String token = jwtProvider.issue(user.getId(), user.getRole());
        return new LoginResponse(token, "Bearer", jwtProvider.getExpiresIn(), UserInfo.from(user));
    }
}
