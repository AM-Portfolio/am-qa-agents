import 'package:am_design_system/am_design_system.dart';
import 'package:flutter/material.dart';

  Color methodBg(String m) {
    switch (m) {
      case 'GET':
        return const Color(0xFF22C55E).withValues(alpha: 0.2);
      case 'POST':
        return AppColors.primary.withValues(alpha: 0.2);
      case 'DELETE':
        return const Color(0xFFEF4444).withValues(alpha: 0.2);
      default:
        return AppColors.primary.withValues(alpha: 0.12);
    }
  }

  Color methodFg(String m) {
    switch (m) {
      case 'GET':
        return const Color(0xFF22C55E);
      case 'DELETE':
        return const Color(0xFFEF4444);
      default:
        return AppColors.primary;
    }
  }

