"""
通報管理ルート
"""

from flask import Blueprint, jsonify, request

from app import csrf, limiter
from app.models import User
from app.services.jwt_auth import jwt_required
from app.services.report_manager import list_reports, review_report, submit_report

reports_bp = Blueprint("reports", __name__)
csrf.exempt(reports_bp)


@reports_bp.route("/api/reports", methods=["POST"])
@limiter.limit("10/hour")
@jwt_required
def submit_report_route():
    data = request.get_json() or {}
    article_id = data.get("article_id")
    if not article_id:
        return jsonify({"error": "記事IDは必須です"}), 400

    try:
        report = submit_report(article_id, request.current_user_id, data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return (
        jsonify({"message": "通報を受け付けました", "report": report.to_dict()}),
        201,
    )


@reports_bp.route("/api/reports", methods=["GET"])
@limiter.limit("120/hour")
@jwt_required
def list_reports_route():
    current_user = User.query.get(request.current_user_id)
    if not current_user or not current_user.is_admin:
        return jsonify({"error": "管理者権限が必要です"}), 403

    status = request.args.get("status")
    reports = list_reports(status=status).all()
    return jsonify({"reports": [report.to_dict() for report in reports]}), 200


@reports_bp.route("/api/reports/<string:report_id>/review", methods=["PUT"])
@limiter.limit("60/hour")
@jwt_required
def review_report_route(report_id):
    data = request.get_json() or {}
    try:
        report = review_report(
            report_id,
            request.current_user_id,
            data.get("status"),
            data.get("resolution"),
        )
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"message": "通報を審査しました", "report": report.to_dict()}), 200
