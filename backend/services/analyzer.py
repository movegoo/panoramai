"""
Competitive analysis and comparison utilities
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from database import Competitor, Ad, InstagramData, AppData


class CompetitiveAnalyzer:
    """Analyze and compare competitor data"""

    def __init__(self, db: Session):
        self.db = db

    def get_instagram_rankings(self) -> List[Dict[str, Any]]:
        """Rank competitors by Instagram metrics"""
        competitors = self.db.query(Competitor).filter(
            Competitor.instagram_username.isnot(None),
            Competitor.is_active == True
        ).all()

        rankings = []
        for competitor in competitors:
            latest = self.db.query(InstagramData).filter(
                InstagramData.competitor_id == competitor.id
            ).order_by(desc(InstagramData.recorded_at)).first()

            if latest:
                rankings.append({
                    "competitor_id": competitor.id,
                    "name": competitor.name,
                    "followers": latest.followers,
                    "engagement_rate": latest.engagement_rate,
                    "posts_count": latest.posts_count
                })

        # Sort by followers
        rankings.sort(key=lambda x: x["followers"], reverse=True)
        for i, r in enumerate(rankings):
            r["rank"] = i + 1

        return rankings

    def get_app_rankings(self, store: str = "playstore") -> List[Dict[str, Any]]:
        """Rank competitors by app store metrics"""
        competitors = self.db.query(Competitor).filter(
            Competitor.is_active == True
        ).all()

        rankings = []
        for competitor in competitors:
            app_id_field = competitor.playstore_app_id if store == "playstore" else competitor.appstore_app_id
            if not app_id_field:
                continue

            latest = self.db.query(AppData).filter(
                AppData.competitor_id == competitor.id,
                AppData.store == store
            ).order_by(desc(AppData.recorded_at)).first()

            if latest:
                rankings.append({
                    "competitor_id": competitor.id,
                    "name": competitor.name,
                    "app_name": latest.app_name,
                    "rating": latest.rating,
                    "reviews_count": latest.reviews_count,
                    "downloads": latest.downloads,
                    "version": latest.version
                })

        # Sort by rating
        rankings.sort(key=lambda x: x["rating"] or 0, reverse=True)
        for i, r in enumerate(rankings):
            r["rank"] = i + 1

        return rankings

    def get_ad_activity_comparison(self) -> List[Dict[str, Any]]:
        """Compare advertising activity across competitors"""
        competitors = self.db.query(Competitor).filter(
            Competitor.facebook_page_id.isnot(None),
            Competitor.is_active == True
        ).all()

        comparison = []
        for competitor in competitors:
            # Count active ads
            active_count = self.db.query(Ad).filter(
                Ad.competitor_id == competitor.id,
                Ad.is_active == True
            ).count()

            # Count total ads
            total_count = self.db.query(Ad).filter(
                Ad.competitor_id == competitor.id
            ).count()

            # Get ads from last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_count = self.db.query(Ad).filter(
                Ad.competitor_id == competitor.id,
                Ad.created_at >= thirty_days_ago
            ).count()

            # Calculate estimated spend
            ads_with_spend = self.db.query(Ad).filter(
                Ad.competitor_id == competitor.id,
                Ad.estimated_spend_min.isnot(None)
            ).all()

            total_spend_min = sum(ad.estimated_spend_min or 0 for ad in ads_with_spend)
            total_spend_max = sum(ad.estimated_spend_max or 0 for ad in ads_with_spend)

            comparison.append({
                "competitor_id": competitor.id,
                "name": competitor.name,
                "active_ads": active_count,
                "total_ads": total_count,
                "ads_last_30_days": recent_count,
                "estimated_spend_min": total_spend_min,
                "estimated_spend_max": total_spend_max
            })

        # Sort by active ads
        comparison.sort(key=lambda x: x["active_ads"], reverse=True)
        return comparison

    def get_growth_trends(self, competitor_id: int, days: int = 30) -> Dict[str, Any]:
        """Calculate growth trends for a competitor"""
        start_date = datetime.utcnow() - timedelta(days=days)

        # Instagram growth
        ig_data = self.db.query(InstagramData).filter(
            InstagramData.competitor_id == competitor_id,
            InstagramData.recorded_at >= start_date
        ).order_by(InstagramData.recorded_at).all()

        instagram_trend = None
        if len(ig_data) >= 2:
            first = ig_data[0]
            last = ig_data[-1]
            if first.followers > 0:
                growth_pct = ((last.followers - first.followers) / first.followers) * 100
                instagram_trend = {
                    "start_followers": first.followers,
                    "end_followers": last.followers,
                    "growth_percent": round(growth_pct, 2),
                    "growth_absolute": last.followers - first.followers
                }

        # App rating trends
        playstore_data = self.db.query(AppData).filter(
            AppData.competitor_id == competitor_id,
            AppData.store == "playstore",
            AppData.recorded_at >= start_date
        ).order_by(AppData.recorded_at).all()

        playstore_trend = None
        if len(playstore_data) >= 2:
            first = playstore_data[0]
            last = playstore_data[-1]
            if first.rating and last.rating:
                playstore_trend = {
                    "start_rating": first.rating,
                    "end_rating": last.rating,
                    "rating_change": round(last.rating - first.rating, 2)
                }

        # Ad activity trend
        ads_in_period = self.db.query(Ad).filter(
            Ad.competitor_id == competitor_id,
            Ad.created_at >= start_date
        ).count()

        return {
            "period_days": days,
            "instagram": instagram_trend,
            "playstore": playstore_trend,
            "new_ads": ads_in_period
        }

    def generate_competitive_report(self) -> Dict[str, Any]:
        """Generate a comprehensive competitive intelligence report"""
        competitors = self.db.query(Competitor).filter(
            Competitor.is_active == True
        ).all()

        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_competitors": len(competitors),
            "instagram_rankings": self.get_instagram_rankings(),
            "playstore_rankings": self.get_app_rankings("playstore"),
            "appstore_rankings": self.get_app_rankings("appstore"),
            "ad_activity": self.get_ad_activity_comparison(),
            "insights": []
        }

        # Generate insights
        if report["instagram_rankings"]:
            top_ig = report["instagram_rankings"][0]
            report["insights"].append(
                f"{top_ig['name']} leads on Instagram with {top_ig['followers']:,} followers"
            )

        if report["playstore_rankings"]:
            top_ps = report["playstore_rankings"][0]
            report["insights"].append(
                f"{top_ps['name']} has the highest Play Store rating: {top_ps['rating']}"
            )

        if report["ad_activity"]:
            most_active = report["ad_activity"][0]
            report["insights"].append(
                f"{most_active['name']} is most active with {most_active['active_ads']} running ads"
            )

        return report
