var index = 0;
var opacity = 1.0;

var slide_transition_time_ms = 6500;
var animation_timeout = 5;
var timer_bar_timeout = undefined;

function transition_slide() {
    transition(0);
    setTimeout(transition_slide, slide_transition_time_ms);
}

callbacks['up'] = () => {
    slide_transition_time_ms -= 100;
    if(slide_transition_time_ms < 500)
        slide_transition_time_ms = 500;
}

callbacks['down'] = () => {
    slide_transition_time_ms += 100;
}

// Then shuffle the array
function shuffleArray(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
}

function next_image() {
    // update the image url
    document.getElementById('slideshow_image').src = image_array[index]['path'];
    // update the folder info
    document.getElementById('image_folder').innerHTML = image_array[index]['folder'];
    // update the date info
    document.getElementById('image_date').innerHTML = image_array[index]['date'];
    index++;
    if(index == image_array.length) { index = 0; }
    animate_timer_bar(slide_transition_time_ms);
}

function transition(step) {
    var element = document.getElementById('slideshow_image');
    if(step == 0) {
        opacity -= 0.1;
        if(opacity <= 0.0) {
            opacity = 0.0;
            step = 1;
        }
        element.style.opacity = opacity;
    } else if(step == 1) {
        next_image();
        step = 2;
    } else if(step == 2) {
        opacity += 0.25;
        if(opacity >= 1.0) {
            opacity = 1.0;
            step = 3;
        }
        element.style.opacity = opacity;
    } else if(step == 3) {
        step = 0;
        return;
    }
    setTimeout(transition, 100, step);
}

function animate_timer_bar(ms) {
    var percent = 100.0;
    var steps = ms/animation_timeout;
    var deltap = 100.0/steps;
    if (timer_bar_timeout)
        clearTimeout(timer_bar_timeout);
    timer_bar_timeout = setTimeout(animate_timer_bar_step, animation_timeout, percent, deltap);
}

function animate_timer_bar_step(percent, deltap) {
    var ele = document.getElementById('timer_bar');
    ele.style.width = ''+percent+'%';
    percent -= deltap;
    if(percent > 0.0)
        timer_bar_timeout = setTimeout(animate_timer_bar_step, animation_timeout, percent, deltap);
}
