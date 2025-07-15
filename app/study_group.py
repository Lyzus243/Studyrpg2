from typing import List
from .models import User, StudyGroup
from sqlalchemy.orm import Session

def create_group(db: Session, name: str, description: str = "") -> StudyGroup:
    group = StudyGroup(name=name, description=description)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group

def join_group(db: Session, user_id: int, group_id: int) -> StudyGroup:
    user = db.query(User).filter(User.id == user_id).first()
    group = db.query(StudyGroup).filter(StudyGroup.id == group_id).first()
    if user and group and user not in group.members:
        group.members.append(user)
        db.commit()
        db.refresh(group)
    return group

def leave_group(db: Session, user_id: int, group_id: int) -> StudyGroup:
    user = db.query(User).filter(User.id == user_id).first()
    group = db.query(StudyGroup).filter(StudyGroup.id == group_id).first()
    if user and group and user in group.members:
        group.members.remove(user)
        db.commit()
        db.refresh(group)
    return group

def get_group_leaderboard(db: Session, group_id: int) -> List[dict]:
    group = db.query(StudyGroup).filter(StudyGroup.id == group_id).first()
    if not group:
        return []
    leaderboard = sorted(
        [{"username": member.username, "xp": member.xp, "level": member.level} for member in group.members],
        key=lambda x: x["xp"],
        reverse=True
    )
    return leaderboard

def list_groups(db: Session) -> List[StudyGroup]:
    return db.query(StudyGroup).all()

def list_user_groups(db: Session, user_id: int) -> List[StudyGroup]:
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        return user.study_groups
    return []