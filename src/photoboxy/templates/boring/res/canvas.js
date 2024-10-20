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
        this.start = { x: undefined, y: undefined };
        
        this.box_color = "#05c4a9";
        this.box_color_hl = "purple";
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
        this.recent = localStorage.getItem("recent");
        console.log(this.recent);
        if(this.recent == undefined || this.recent == "") {
            this.recent = [];
            localStorage.setItem("recent", JSON.stringify(this.recent));
        } else {
            this.recent = JSON.parse(this.recent);
        }
        this.renderRecent();
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

    updateRecent(name) {
        console.log("updateRecent", name);
        if( this.recent.indexOf(name) > -1 ) {
            return;
        }
        this.recent.unshift(name);
        if( this.recent.length > 10) this.recent.pop();
        localStorage.setItem("recent", JSON.stringify(this.recent));
        this.renderRecent();
    };

    renderRecent() {
        let html = "<table>";
        this.recent.forEach( (name, index) => {
            html += `<tr><th>${index}</th><td>${name}</td></tr>`;
        })
        html += "</table>";
        $("#recent").html(html);
    };

    drawTags() {
        let color_map = {};
        let box_color = this.box_color;
        let box_color_hl = this.box_color_hl;
        let ctx = this.canvas.getContext("2d");
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.tags.forEach( (tag, i) => {
            if(tag == undefined) return;
            ctx.beginPath();
            ctx.lineWidth = "2";
            ctx.strokeStyle = box_color;
            if(i == this.current_tag) {
                ctx.lineWidth = "4";
                ctx.strokeStyle = box_color_hl;
            }
            ctx.rect(tag.left, tag.top, tag.width, tag.height);
            ctx.stroke();

            ctx.beginPath();
            ctx.textAlign = "center";
            ctx.textBaseline = "bottom";
            ctx.font = "16px Verdana Bold";
            ctx.fillStyle = box_color;
            if(i == this.current_tag) ctx.fillStyle = box_color_hl;
            //let textWidth = ctx.measureText(tag.name).width;
            ctx.fillText(tag.name, tag.left + (tag.width/2), tag.top)
            ctx.stroke();
        });
    };

    // draws the current box that the user is trying to size as a first step to adding a new tag
    drawBox(left, top, width, height) {
        var ctx = this.canvas.getContext("2d");
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        ctx.beginPath();
        ctx.lineWidth = "4";
        ctx.fillStyle = "rgba(199, 87, 231, 0.2)";
        ctx.strokeStyle = this.box_color;
        ctx.rect(left, top, width, height);
        ctx.fill();
        ctx.stroke();
    };

    //mousedown connected functions -- START
    inBox(x, y, r) {
        return (x>r.left && x<(r.width+r.left)) && (y>r.top && y<(r.top+r.height));
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
       
        let found = false;
        myself.tags.forEach( (tag, i) => {
            if(myself.inBox(mouseX, mouseY, tag)) {
                myself.selectTag(i);
                found = true;
            }
        });
        if(!found) {
            myself.start.x = mouseX;
            myself.start.y = mouseY;
        }
    };
     
    mouseMove(e) {    
        let canvas = e.target;
        let myself = canvas.facetag_manager;
        if(myself.start.x == undefined) {
            return;
        }
        e.preventDefault();
        e.stopPropagation();

        let pos = myself.getMousePos(canvas, e);
        let mouseX = pos.x;
        let mouseY = pos.y;

        let left = Math.min( ...[myself.start.x, mouseX]);
        let top = Math.min( ...[myself.start.y, mouseY]);

        let width = Math.abs(mouseX - myself.start.x);
        let height = Math.abs(mouseY - myself.start.y);
        myself.drawBox(left, top, width, height);
    };

    mouseUp(e) {
        let myself = e.target.facetag_manager;
        if(myself.start.x == undefined) {
            return;
        }
        e.preventDefault();
        e.stopPropagation();

        let pos = myself.getMousePos(canvas, e);
        let mouseX = pos.x;
        let mouseY = pos.y;

        let c = myself.start;

        let left = Math.min( ...[c.x, mouseX]);
        let top = Math.min( ...[c.y, mouseY]);

        let width = Math.abs(mouseX - c.x);
        let height = Math.abs(mouseY - c.y);

        c.l = left;
        c.t = top;
        c.w = width;
        c.h = height;
        $( "#name_dialog" ).dialog( "open" );
        $( "#name" ).focus()
        myself.start.x = undefined;
    };

    keyHandler(e) {
        let canvas = document.getElementById('canvas');
        let myself = canvas.facetag_manager;
        e = e || window.event;
        if ($( "#retag_dialog" ).dialog( "isOpen" )) return;
        if ($( "#name_dialog" ).dialog( "isOpen" )) return;
        if ($( "#rename_dialog" ).dialog( "isOpen" )) return;

        if (e.key == "F2") {
            if (myself.current_tag == undefined) return;
            $( "#retag_dialog" ).dialog( "open" );
            $( "#retag" ).focus();
        } else if (e.key == "r") {
            if (myself.current_tag == undefined) return;
            e.preventDefault();
            e.stopPropagation();
            $( "#rename_dialog" ).dialog( "open" );
            $( "#rename" ).focus()
        } else if (e.key == "Delete") {
            if (myself.current_tag == undefined) return;
            myself.deleteTag(myself.current_tag);
        } else if (e.key == "u") {
            let n = myself.tags.length;
            for(var i=0; i<n; i++) {
                myself.deleteTag(0);
            }
        } else if (e.key == "n") {
            window.location = $( "#next" )[0].href;
        } else if (e.key == "p") {
            window.location = $( "#prev" )[0].href;
        } else if (e.key == "x") {
            if (myself.current_tag == undefined || myself.current_tag == myself.tags.length - 1) {
                myself.current_tag = 0;
            } else {
                myself.current_tag += 1;
            }
            myself.drawTags();
        } else if (e.keyCode >= 48 && e.keyCode <= 57) {
            if (myself.current_tag == undefined) return;
            e.preventDefault();
            e.stopPropagation();
            let offset = e.keyCode - 48;
            if(offset > myself.recent.length - 1) return;
            let newname = myself.recent[offset];
            myself.renameTag(myself.current_tag, newname);
        } else if (e.keyCode >= 96 && e.keyCode <= 105) {
            if (myself.current_tag == undefined) return;
            e.preventDefault();
            e.stopPropagation();
            let offset = e.keyCode - 96;
            if(offset > myself.recent.length - 1) return;
            let newname = myself.recent[offset];
            myself.renameTag(myself.current_tag, newname);
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
        myself.updateRecent(response.name);
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
        //myself.updateRecent(response.name);
    };

    newtag_call(name, left, top, width, height) {
        let url = '/tag';
        let data = {
            src_filename: this.src_filename,
            name: name,
            left: left,
            top: top,
            width: width,
            height: height
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
        let c = myself.start;
        myself.addTag(face_id, name, c.l, c.t, c.w, c.h);
        //myself.updateRecent(name);
        Object.keys(c).forEach( (k) => {c[k] = undefined });
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
    };

    deltag_cb(response) {
        let canvas = document.getElementById('canvas');
        let myself = canvas.facetag_manager;
        myself.tags.splice(myself.current_tag, 1);
        myself.current_tag = undefined;
        myself.drawTags();
    };

};