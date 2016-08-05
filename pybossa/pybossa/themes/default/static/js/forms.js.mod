(function(){
    var resource = location.pathname.split('/')[1];

    function makeSlug(text) {
        var not_valid_chars = /([$#%·~!¡?"¿'=)(!&\/|]+)/g;
        return text.toLowerCase().trim().replace(not_valid_chars, "").replace(/( )+/g, "");
    }

    if ( resource === 'project' ) {
        $("#name").on('keyup', function () {
          var text = $(this).val();
          $('#short_name').val(makeSlug($(this).val()));
        });
    }

    if ( resource === 'account' ) {
        $("#fullname").on('keyup', function () {
          var text = $(this).val();
          $('#name').val(makeSlug($(this).val()));
        });
        $("#password").change(function () {
            var pwd = $(this).val();
            alert("password entered is: " + pwd)
            len = pwd.length;
            alert("password length: " + len);
            if (len < 8 || len > 15) {
                alert("password must be between 8 to 15 character length");
            }


            var std_scores = {0: 'Very Poor', 1: 'Weak', 2: 'Medium', 3: 'Average', 4: 'Strong'};
            var strength = {'has_upper':false, 'has_lower':false, 'has_num':false, 'has_special':false};
            var pattern_upper = new RegExp("[A-Z]");
            var pattern_lower = new RegExp("[a-z]");
            var pattern_num = new RegExp("[0-9]");
            var pattern_special = new RegExp("[!@#$%^&*]");

            strength['has_upper'] = pattern_upper.test(pwd);
            strength['has_lower'] = pattern_lower.test(pwd);
            strength['has_num'] = pattern_num.test(pwd);
            strength['has_special'] = pattern_special.test(pwd);

            var score = 0;
            for (var k in strength) {
                if (strength[k]){
                    score++;
                }
            }

            alert("score is: " + score);

        });
    }

}());

