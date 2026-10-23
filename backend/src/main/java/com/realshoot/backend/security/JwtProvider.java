package com.realshoot.backend.security;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;

import javax.crypto.SecretKey;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import com.realshoot.backend.auth.Role;
import com.realshoot.backend.global.error.ApiException;
import com.realshoot.backend.global.error.ErrorCode;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

/** HS256 JWT. 클레임: sub(users.id), role, iat, exp. RAG 서비스와 같은 JWT_SECRET 사용 */
@Component
public class JwtProvider {

    private static final String BEARER_PREFIX = "Bearer ";

    private final SecretKey key;
    private final long expiresIn;

    public JwtProvider(@Value("${jwt.secret}") String secret, @Value("${jwt.expires-in}") long expiresIn) {
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.expiresIn = expiresIn;
    }

    public String issue(Long userId, Role role) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(String.valueOf(userId))
                .claim("role", role.name())
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plusSeconds(expiresIn)))
                .signWith(key, Jwts.SIG.HS256)
                .compact();
    }

    /** 서명 · 만료 · 클레임 형식이 하나라도 틀리면 401 */
    public AuthUser parse(String token) {
        try {
            Claims claims = Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
            return new AuthUser(Long.valueOf(claims.getSubject()), Role.valueOf(claims.get("role", String.class)));
        } catch (JwtException | IllegalArgumentException | NullPointerException e) {
            throw new ApiException(ErrorCode.UNAUTHORIZED, "유효하지 않은 토큰입니다.");
        }
    }

    /** {@code Bearer <JWT>} 헤더 값 → 사용자. 형식이 틀리면 401 */
    public AuthUser parseBearer(String authorizationHeader) {
        if (authorizationHeader == null || !authorizationHeader.startsWith(BEARER_PREFIX)) {
            throw new ApiException(ErrorCode.UNAUTHORIZED);
        }
        return parse(authorizationHeader.substring(BEARER_PREFIX.length()).trim());
    }

    public long getExpiresIn() {
        return expiresIn;
    }
}
