"""Zone priority service for pressure-based zone ordering.

Determines the order of zones to relieve based on pressure values
and duration of pressure application.
"""

import logging
from typing import List, Tuple, Dict, Optional

from ..domain.enums import PostureType

logger = logging.getLogger(__name__)


class ZonePriorityService:
    """압력값과 지속시간 기반으로 존 우선순위 결정."""

    # 신체 부위 → 존 매핑
    # Zone 1: 상체 상단 (1사분면 - 우측 상단)
    # Zone 2: 상체 하단 (2사분면 - 좌측 상단)
    # Zone 3: 하체 상단 (3사분면 - 좌측 하단)
    # Zone 4: 하체 하단 (4사분면 - 우측 하단)
    BODY_PART_TO_ZONE: Dict[str, int] = {
        "occiput": 1,  # 후두부
        "scapula": 1,  # 견갑골
        "right_elbow": 2,  # 오른쪽 팔꿈치
        "left_elbow": 2,  # 왼쪽 팔꿈치
        "sacrum": 3,  # 천골
        "right_heel": 4,  # 오른쪽 발뒤꿈치
        "left_heel": 4,  # 왼쪽 발뒤꿈치
    }

    # 기본 릴리프 시간 설정 (초)
    BASE_RELIEF_TIME = 5
    HIGH_PRESSURE_THRESHOLD = 80
    MEDIUM_PRESSURE_THRESHOLD = 50
    LONG_DURATION_THRESHOLD = 300  # 5분

    def determine_zone_order(
        self,
        pressures: Dict[str, int],
        durations: Dict[str, int],
        posture: PostureType = PostureType.SUPINE,
        forced_orders: Optional[List[int]] = None,
    ) -> List[Tuple[int, int]]:
        """압력값과 지속시간을 기반으로 존 순서 결정.

        서버에서 강제 순서(forced_orders)가 지정된 경우 해당 순서를 우선 적용.
        강제 순서가 없는 경우 압력 기반으로 우선순위 계산.

        우선순위 점수 = 압력값 + (지속시간/60) * 10
        점수가 높은 존부터 순서대로 릴리프 실행.

        Args:
            pressures: 신체 부위별 압력값 {"occiput": 85, "sacrum": 70, ...}
            durations: 신체 부위별 지속시간(초) {"occiput": 300, ...}
            posture: 현재 자세 (향후 자세별 매핑 확장 가능)
            forced_orders: 서버에서 지정한 강제 존 순서 [1, 2, 3, 4]

        Returns:
            [(zone_number, relief_duration_seconds), ...] 우선순위 순
        """
        # 서버에서 강제 순서가 지정된 경우
        if forced_orders:
            logger.info(f"Using forced zone order from server: {forced_orders}")
            return self._apply_forced_order(forced_orders, pressures, durations)

        zone_scores: Dict[int, Tuple[float, int, int]] = {}

        for body_part, pressure in pressures.items():
            if body_part not in self.BODY_PART_TO_ZONE:
                continue
            if pressure <= 0:
                continue

            zone = self.BODY_PART_TO_ZONE[body_part]
            duration = durations.get(body_part, 0)

            # 우선순위 점수 계산: 압력 + 지속시간 가중치
            score = pressure + (duration / 60) * 10

            # 존별 최대값 유지 (여러 부위가 같은 존에 매핑될 수 있음)
            if zone not in zone_scores or score > zone_scores[zone][0]:
                zone_scores[zone] = (score, pressure, duration)

        # 점수 높은 순으로 정렬
        sorted_zones = sorted(
            zone_scores.items(),
            key=lambda x: x[1][0],
            reverse=True,
        )

        # (존 번호, 릴리프 시간) 리스트 생성
        result = [
            (zone, self._calculate_relief_time(data[1], data[2]))
            for zone, data in sorted_zones
        ]

        logger.info(f"Zone order determined: {result}")
        return result

    def _calculate_relief_time(self, pressure: int, duration: int) -> int:
        """압력과 지속시간 기반 릴리프 시간 계산.

        Args:
            pressure: 압력값 (0-100)
            duration: 지속시간 (초)

        Returns:
            릴리프 시간 (초)
        """
        relief_time = self.BASE_RELIEF_TIME

        # 압력이 높으면 릴리프 시간 증가
        if pressure > self.HIGH_PRESSURE_THRESHOLD:
            relief_time += 10
        elif pressure > self.MEDIUM_PRESSURE_THRESHOLD:
            relief_time += 5

        # 지속시간이 길면 릴리프 시간 증가
        if duration > self.LONG_DURATION_THRESHOLD:
            relief_time += 5

        return relief_time

    def _apply_forced_order(
        self,
        forced_orders: List[int],
        pressures: Dict[str, int],
        durations: Dict[str, int],
    ) -> List[Tuple[int, int]]:
        """서버 강제 순서를 적용하여 존 시퀀스 생성.

        강제 순서의 각 존에 대해 압력 데이터 기반으로 릴리프 시간 계산.
        압력 데이터가 없는 존은 기본 릴리프 시간 적용.

        Args:
            forced_orders: 서버 지정 존 순서 [1, 2, 3, 4]
            pressures: 신체 부위별 압력값
            durations: 신체 부위별 지속시간

        Returns:
            [(zone_number, relief_duration_seconds), ...] 강제 순서대로
        """
        # 존별 최대 압력/지속시간 계산
        zone_data: Dict[int, Tuple[int, int]] = {}
        for body_part, pressure in pressures.items():
            if body_part not in self.BODY_PART_TO_ZONE:
                continue
            zone = self.BODY_PART_TO_ZONE[body_part]
            duration = durations.get(body_part, 0)

            if zone not in zone_data or pressure > zone_data[zone][0]:
                zone_data[zone] = (pressure, duration)

        # 강제 순서대로 시퀀스 생성
        result = []
        for zone_num in forced_orders:
            if zone_num < 1 or zone_num > 4:
                logger.warning(f"Invalid zone number in forced_orders: {zone_num}")
                continue

            if zone_num in zone_data:
                pressure, duration = zone_data[zone_num]
                relief_time = self._calculate_relief_time(pressure, duration)
            else:
                # 압력 데이터 없으면 기본 시간
                relief_time = self.BASE_RELIEF_TIME

            result.append((zone_num, relief_time))

        logger.info(f"Forced zone order applied: {result}")
        return result
