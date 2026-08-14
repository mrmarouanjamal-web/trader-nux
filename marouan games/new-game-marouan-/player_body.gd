extends CharacterBody2D

# ===== VARIABLES =====
var speed := 200.0
var gravity := 900.0
var jump_force := -400.0
var is_stopped := false
var is_attacking := false

@onready var attack_area = $AttackArea
@onready var sprite = $AnimatedSprite2D

# ===== PHYSICS =====
func _physics_process(delta):
	# STOP
	if Input.is_action_pressed("stop"):
		is_stopped = true
	else:
		is_stopped = false

	# MOVE
	if is_stopped:
		velocity.x = 0
	else:
		var direction = Input.get_axis("ui_left", "ui_right")
		velocity.x = direction * speed

		if direction != 0:
			sprite.flip_h = direction < 0

		if Input.is_action_just_pressed("ui_up") and is_on_floor():
			velocity.y = jump_force

	# ATTACK
	if Input.is_action_just_pressed("attack") and not is_attacking:
		attack()  # ✅ صححنا الاسم هنا

	# APPLY GRAVITY
	velocity.y += gravity * delta
	move_and_slide()

# ===== ATTACK FUNCTION =====
func attack():
	print("Attack triggered")
	is_attacking = true
	
	# بيّن السيف وفعّل الرادار ديالو
	attack_area.visible = true
	attack_area.monitoring = true 
	
	await get_tree().create_timer(0.2).timeout
	
	# خبي السيف وطفي الرادار
	attack_area.visible = false
	attack_area.monitoring = false
	is_attacking = false

func _on_attack_area_body_entered(body):
	# واش هادا اللي قسناه عندو بطاقة "enemies"؟
	if body.is_in_group("enemies"):
		print("Enemy hit!") # باش تأكد
		body.queue_free()   # مسحو من الوجود
