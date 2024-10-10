class FaceTagManager {
    constructor(canvas, image, src_filename) {
        this.canvas = canvas;
        canvas.facetag_manager = this; //saved for callbacks
        this.image = image;
        this.src_filename = src_filename;
        this.tags = [];
        this.current_tag = undefined;
        this.current_box = {};
        this.drag = { tr: false, tl: false, br: false, bl: false, wr: false };
        this.start = { x: 0, y: 0 };
        
        this.box_color = "#05c4a9";
        this.handleRadius = 10;
        this.minimum_width = 25;

        canvas.height = image.height;
        canvas.width = image.width;
        canvas.style.top = image.offsetTop + "px";
        canvas.style.left = image.offsetLeft + "px";

        canvas.addEventListener('mousedown', this.mouseDown, false);
        canvas.addEventListener('mouseup', this.mouseUp, false);
        canvas.addEventListener('mousemove', this.mouseMove, false);
        canvas.addEventListener('touchstart', this.mouseDown);
        canvas.addEventListener('touchmove', this.mouseMove);
        canvas.addEventListener('touchend', this.mouseUp);

        document.addEventListener('keydown', this.keyHandler);
    };

    addTag(face_id, name, left, top, width, height) {
        this.tags.push( { face_id: face_id, name: name, left: left, top: top, width: width, height: height} );
    };

    selectTag(tag_id) {
        this.current_tag = tag_id;
        this.drawTags();
    };

    renameTag(tag_id, name) {
        let tag = this.tags[tag_id];
        let face_id = this.retag_call(tag.face_id, name, tag.left + 1, tag.top + 1 );
        tag.face_id = face_id;
        tag.name = name;
    };

    renameFace(tag_id, name) {
        let tag = this.tags[tag_id];
        let face_id = this.rename_call(tag.face_id, name, tag.left + 1, tag.top + 1 );
        tag.name = name;
    };

    deleteTag(tag_id) {
        let tag = this.tags[tag_id];
        let face_id = tag.face_id;
        this.deltag_call(face_id, tag.left + 1, tag.top + 1)
    };

    newBox() {
        this.current_box = {
            left: (this.canvas.width/2) - 10,
            top: (this.canvas.height/2) - 10,
            width: 20,
            height: 20
        };
    };

    delBox() {
        this.current_box = {};
    };

    drawTags() {
        let color_map = {};
        let box_color = this.box_color;
        let ctx = this.canvas.getContext("2d");
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.tags.forEach( (tag, i) => {
            if(tag == undefined) return;
            ctx.beginPath();
            ctx.lineWidth = "2";
            if(i == this.current_tag) ctx.lineWidth = "4";
            ctx.strokeStyle = box_color;
            ctx.rect(tag.left, tag.top, tag.width, tag.height);
            ctx.stroke();

            ctx.beginPath();
            ctx.textAlign = "center";
            ctx.textBaseline = "bottom";
            ctx.font = "14px Verdana";
            ctx.fillStyle = box_color;
            //let textWidth = ctx.measureText(tag.name).width;
            ctx.fillText(tag.name, tag.left + (tag.width/2), tag.top)
            ctx.stroke();
        });
    };

    drawCircle(x, y, radius) {
        let ctx = this.canvas.getContext("2d");
        ctx.fillStyle = this.box_color;
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, 2 * Math.PI);
        ctx.fill();
    };

    drawHandles() {
        let rect = this.current_box;
        let handleRadius = this.handleRadius;
        this.drawCircle(rect.left, rect.top, handleRadius);
        this.drawCircle(rect.left + rect.width, rect.top, handleRadius);
        this.drawCircle(rect.left + rect.width, rect.top + rect.height, handleRadius);
        this.drawCircle(rect.left, rect.top + rect.height, handleRadius);
    };

    // draws the current box that the user is trying to size as a first step to adding a new tag
    drawBox() {
        if(this.current_box.left == undefined) return;
        let rect = this.current_box;
        var ctx = this.canvas.getContext("2d");
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        ctx.beginPath();
        ctx.lineWidth = "4";
        ctx.fillStyle = "rgba(199, 87, 231, 0.2)";
        ctx.strokeStyle = this.box_color;
        ctx.rect(rect.left, rect.top, rect.width, rect.height);
        ctx.fill();
        ctx.stroke();
        this.drawHandles();
    };

    mouseUp(e) {
        let myself = e.target.facetag_manager;
        Object.keys(myself.drag).forEach( (k,i) => { myself.drag[k] = false });
    };
    
    //mousedown connected functions -- START
    inBox(x, y, r) {
        return (x>r.left && x<(r.width+r.left)) && (y>r.top && y<(r.top+r.height));
    };
    
    closeEnough(p1, p2) {
        return Math.abs(p1 - p2) < this.handleRadius;
    };
    
    getMousePos(canvas, evt) {
        var clx, cly;
        if (evt.type == "touchstart" || evt.type == "touchmove") {
            clx = evt.touches[0].clientX;
            cly = evt.touches[0].clientY;
        } else {
            clx = evt.clientX;
            cly = evt.clientY;
        }
        let boundingRect = canvas.getBoundingClientRect();
        return {
            x: clx - boundingRect.left,
            y: cly - boundingRect.top
        };
    };
    
    mouseDown(e) {
        let canvas = e.target;
        let myself = canvas.facetag_manager;
        let pos = myself.getMousePos(canvas, e);
        let mouseX = pos.x;
        let mouseY = pos.y;
        let rect = myself.current_box;

        // first check the current_box, then all the tags

        if (rect.left != undefined) {
            // 0. inside movable rectangle
            if (myself.inBox(mouseX, mouseY, rect)){
                myself.drag.wr = true;
                myself.start.x = mouseX
                myself.start.y = mouseY
            }
            // 1. top left
            else if (myself.closeEnough(mouseX, rect.left) && myself.closeEnough(mouseY, rect.top)) {
                myself.drag.tl = true;
            }
            // 2. top right
            else if (myself.closeEnough(mouseX, rect.left + rect.width) && myself.closeEnough(mouseY, rect.top)) {
                myself.drag.tr = true;
            }
            // 3. bottom left
            else if (myself.closeEnough(mouseX, rect.left) && myself.closeEnough(mouseY, rect.top + rect.height)) {
                myself.drag.bl = true;
            }
            // 4. bottom right
            else if (myself.closeEnough(mouseX, rect.left + rect.width) && myself.closeEnough(mouseY, rect.top + rect.height)) {
                myself.drag.br = true;
            }
            // (5.) none of them
            else {
                // handle not resizing
            }
            myself.drawBox();
        } else {
            myself.tags.forEach( (tag, i) => {
                if(myself.inBox(mouseX, mouseY, tag)) {
                    myself.selectTag(i);
                }
            });
        }
    };
     
    mouseMove(e) {    
        let canvas = e.target;
        let myself = canvas.facetag_manager;
        let pos = myself.getMousePos(canvas, e);
        let mouseX = pos.x;
        let mouseY = pos.y;
        let rect = myself.current_box;

        if (myself.drag.wr) {
            e.preventDefault();
            e.stopPropagation();
            let dx = mouseX - myself.start.x;
            let dy = mouseY - myself.start.y;
            if ((rect.left+dx)>0 && (rect.left+dx+rect.width)<canvas.width) {
                rect.left += dx;
            }
            if ((rect.top+dy)>0 && (rect.top+dy+rect.height)<canvas.height) {
                rect.top += dy;
            }
            myself.start.x = mouseX;
            myself.start.y = mouseY;
        } else if (myself.drag.tl) {
            e.preventDefault();
            e.stopPropagation();
            let x1 = rect.left;
            let x2 = x1 + rect.width;
            let y1 = rect.top;
            let y2 = y1 + rect.height;

            if( mouseX < x2 - myself.minimum_width ) {
                rect.left = mouseX;
                rect.width = x2 - mouseX;
            }
            if( mouseY < y2 - myself.minimum_width ) {
                rect.top = mouseY;
                rect.height = y2 - mouseY;
            }
        } else if (myself.drag.tr) {
            e.preventDefault();
            e.stopPropagation();


            let x1 = rect.left;
            let x2 = x1 + rect.width;
            let y1 = rect.top;
            let y2 = y1 + rect.height;

            if( mouseX > x1 + myself.minimum_width ) {
                rect.width = mouseX - x1;
            }
            if( mouseY < y2 - myself.minimum_width ) {
                rect.top = mouseY;
                rect.height = y2 - mouseY;
            }
        } else if (myself.drag.bl) {
            e.preventDefault();
            e.stopPropagation();

            let x1 = rect.left;
            let x2 = x1 + rect.width;
            let y1 = rect.top;
            let y2 = y1 + rect.height;

            if( mouseX < x2 - myself.minimum_width ) {
                rect.left = mouseX;
                rect.width = x2 - mouseX;
            }
            if( mouseY > y1 + myself.minimum_width ) {
                rect.height = mouseY - y1;
            }
        } else if (myself.drag.br) {
            e.preventDefault();
            e.stopPropagation();
            rect.width = mouseX - rect.left;
            rect.height = mouseY - rect.top;
            if(rect.width < myself.minimum_width) rect.width = myself.minimum_width
            if(rect.height < myself.minimum_width) rect.height = myself.minimum_width
        }
        myself.drawBox();
    };

    keyHandler(e) {
        let canvas = document.getElementById('canvas');
        let myself = canvas.facetag_manager;
        e = e || window.event;
        if (e.key == "F2") {
            if(myself.current_tag == undefined) return;
            let newname = prompt("Who is this?");
            if(newname.length > 0) {
                myself.renameTag(myself.current_tag, newname);
            }
        } else if (e.key == "Insert") {
            myself.newBox()
            myself.drawBox()
        } else if (e.key == "r") {
            if(myself.current_tag == undefined) return;
            let newname = prompt("Who is this?");
            if(newname.length > 0) {
                myself.renameFace(myself.current_tag, newname);
            }
        } else if (e.key == "Delete") {
            if(myself.current_tag == undefined) return;
            myself.deleteTag(myself.current_tag);
        } else if (e.key == "+") {
            if(myself.current_box.left == undefined) return;
            let newname = prompt("Who is this?");
            if(newname.length > 0) {
                myself.newtag_call(newname);
            }
        } else if (e.key == "?") {
        } else {
            console.log(e);
        }
    };

    ajax(url, data, cb) {
        let post = JSON.stringify(data)
        let xhr = new XMLHttpRequest();

        xhr.open('POST', url, true);
        xhr.setRequestHeader('Content-type', 'application/json; charset=UTF-8')
        xhr.send(post)
        xhr.onload = (resp) => {
            cb(JSON.parse(resp.explicitOriginalTarget.response));
        };
    };

    retag_call(face_id, name, left, top) {
        let url = `/retag`;
        let data = { 
            src_filename: this.src_filename, 
            face_id: face_id, 
            name: name, 
            x: left, 
            y: top 
        };
        this.ajax(url, data, this.retag_cb);
    };

    retag_cb(response) {
        let canvas = document.getElementById('canvas');
        let myself = canvas.facetag_manager;
        let tag = myself.tags[myself.current_tag];
        tag['face_id'] = response.new_face_id;
        tag['name'] = response.name;
        myself.drawTags();
    };

    rename_call(face_id, name, left, top) {
        let url = "/rename";
        let data = { face_id: face_id, name: name };
        this.ajax(url, data, this.rename_cb);
    };

    rename_cb(response) {
        let canvas = document.getElementById('canvas');
        let myself = canvas.facetag_manager;
        let tag = myself.tags[myself.current_tag];
        tag['face_id'] = response.new_face_id;
        tag['name'] = response.name;
        myself.drawTags();
    };

    newtag_call(name) {
        let url = '/tag';
        let data = {
            src_filename: this.src_filename,
            name: name,
            left: this.current_box.left,
            top: this.current_box.top,
            width: this.current_box.width,
            height: this.current_box.height
        };
        this.ajax(url, data, this.newtag_cb);
    };

    newtag_cb(response) {
        if(response.status == 'pending') return;
        console.log(response);
        let face_id = response.face_id;
        let name = response.name;
        let canvas = document.getElementById('canvas');
        let myself = canvas.facetag_manager;
        myself.addTag(face_id, name, myself.current_box.left, myself.current_box.top, myself.current_box.width, myself.current_box.height)
        myself.current_box = {};
        myself.drawTags();
    };

    deltag_call(face_id, x, y) {
        let url = `/untag`;
        let data = {
            src_filename: this.src_filename,
            face_id: face_id,
            x: x,
            y: y
        };
        this.ajax(url, data, this.deltag_cb);
    }

    deltag_cb(response) {
        let canvas = document.getElementById('canvas');
        let myself = canvas.facetag_manager;
        myself.tags.pop(myself.current_tag);
        myself.current_tag = undefined;
        myself.drawTags();
    }

};