package com.realshoot.backend.security;

import java.security.Principal;
import java.util.List;

import org.springframework.security.core.authority.SimpleGrantedAuthority;

import com.realshoot.backend.auth.Role;

/** JWT에서 꺼낸 로그인 사용자. REST(SecurityContext)와 STOMP(simpUser) 모두 이 타입 */
public record AuthUser(Long id, Role role) implements Principal {

    @Override
    public String getName() {
        return String.valueOf(id);
    }

    public boolean isAdmin() {
        return role == Role.ADMIN;
    }

    public List<SimpleGrantedAuthority> authorities() {
        return List.of(new SimpleGrantedAuthority("ROLE_" + role.name()));
    }
}
