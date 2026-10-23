package com.realshoot.backend.rag;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

public interface ManualRefRepository extends JpaRepository<ManualRef, Long> {

    List<ManualRef> findByCall_IdOrderByIdAsc(Long callPk);
}
